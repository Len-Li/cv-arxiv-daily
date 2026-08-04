import argparse
import json
import logging
import os
import re
import tempfile

import arxiv
import yaml


logging.basicConfig(
    format='[%(asctime)s %(levelname)s] %(message)s',
    datefmt='%m/%d/%Y %H:%M:%S',
    level=logging.INFO,
)

ARXIV_PDF_URL = "https://arxiv.org/pdf/"

OR = ' OR '
AND = ' AND '
ANDNOT = ' ANDNOT '


def quote_query_terms(terms):
    quoted = []
    for term in terms:
        prefix, separator, value = term.partition(':')
        if separator:
            value = value.strip()
            quoted.append(f"{prefix}:{value}" if ' ' not in value else f'{prefix}:"{value}"')
        else:
            quoted.append(term if ' ' not in term else f'"{term}"')
    return OR.join(quoted)


def build_query(topic_config):
    """Build an arXiv query without mutating the loaded YAML configuration."""
    clauses = []
    filters = topic_config.get('filters', [])
    if filters:
        clauses.append(f"({quote_query_terms(filters)})")

    for field, terms in topic_config.items():
        if field in ('filters', 'invert'):
            continue
        clauses.append(f"({quote_query_terms(terms)})")

    inverted = topic_config.get('invert', [])
    if inverted:
        if not clauses:
            raise ValueError("An inverted query requires at least one positive clause")
        return f"{AND.join(clauses)}{ANDNOT}({quote_query_terms(inverted)})"

    return AND.join(clauses)


def load_config(config_file):
    with open(config_file, 'r', encoding='utf-8') as config_handle:
        config = yaml.safe_load(config_handle)
    config['queries'] = {
        topic: build_query(topic_config)
        for topic, topic_config in config['keywords'].items()
    }
    return config


def first_author(authors):
    return str(authors[0]) if authors else "Unknown"


def normalize_author(author):
    author = str(author or "").strip()
    author = re.sub(r"(?:\s+et\.al\.)+\s*$", "", author,
                    flags=re.IGNORECASE)
    return f"{author} et.al." if author else "Unknown et.al."


def strip_outer_bold(value):
    value = str(value or "").strip()
    if len(value) >= 4 and value.startswith("**") and value.endswith("**"):
        return value[2:-2]
    return value


def parse_paper_entry(entry):
    """Read the compact tab-separated format consumed by papers-json.html."""
    text = str(entry or "").rstrip("\r\n")
    tab_parts = text.split("\t")
    if len(tab_parts) >= 3:
        date_value, title_value, author_value = tab_parts[:3]
    else:
        pipe_parts = [part.strip() for part in text.split("|")]
        if pipe_parts and not pipe_parts[0]:
            pipe_parts.pop(0)
        if pipe_parts and not pipe_parts[-1]:
            pipe_parts.pop()
        if len(pipe_parts) < 3:
            raise ValueError("paper entry must contain date, title, and author fields")
        date_value, title_value, author_value = pipe_parts[:3]

    date = strip_outer_bold(date_value)
    title = strip_outer_bold(title_value)
    author = str(author_value or "").strip()
    if not date or not title or not author:
        raise ValueError("paper entry contains an empty date, title, or author")
    return date, title, author


def format_paper_entry(date, title, author, paper_id):
    pdf_url = f"{ARXIV_PDF_URL}{paper_id}.pdf"
    return (f"**{date}**\t**{title}**\t{normalize_author(author)}\t"
            f"[{paper_id}]({pdf_url})\n")


def normalize_paper_entry(entry, paper_id):
    """Repair legacy formatting and remove no-longer-used code-link fields."""
    date, title, author = parse_paper_entry(entry)
    return format_paper_entry(date, title, author, paper_id)


def get_daily_papers(topic, query, max_results, max_pages):
    """Fetch one topic and return the entries to merge into the web JSON."""
    papers = {}
    if max_results <= 0 or max_pages <= 0:
        return {topic: papers}

    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=max_results * max_pages,
        sort_by=arxiv.SortCriterion.SubmittedDate,
    )
    for result in client.results(search):
        paper_id = result.get_short_id()
        paper_key = re.sub(r"v\d+$", "", paper_id)
        updated = result.updated.date()
        title = result.title
        author = first_author(result.authors)
        logging.info("topic=%s updated=%s title=%s", topic, updated, title)
        papers[paper_key] = format_paper_entry(updated, title, author, paper_key)

    return {topic: papers}


def read_json(filename):
    with open(filename, 'r', encoding='utf-8') as json_handle:
        return json.load(json_handle)


def write_json(filename, data):
    """Atomically replace the web data file after a complete JSON write."""
    target_path = os.fspath(filename)
    target_dir = os.path.dirname(os.path.abspath(target_path))
    prefix = f".{os.path.basename(target_path)}."
    descriptor, temporary_path = tempfile.mkstemp(
        prefix=prefix, suffix=".tmp", dir=target_dir, text=True)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as json_handle:
            json.dump(data, json_handle)
            json_handle.flush()
            os.fsync(json_handle.fileno())
        os.replace(temporary_path, target_path)
    except Exception:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)
        raise


def update_json_file(filename, topic_updates):
    data = read_json(filename)
    for update in topic_updates:
        for topic, papers in update.items():
            data.setdefault(topic, {}).update(papers)
    write_json(filename, data)


def repair_paper_entries(filename):
    """Repair legacy entries without making network requests."""
    data = read_json(filename)
    repaired = 0
    for papers in data.values():
        for paper_id, entry in papers.items():
            try:
                normalized = normalize_paper_entry(entry, paper_id)
            except ValueError as error:
                raise ValueError(
                    f"Unable to repair paper {paper_id}: {error}"
                ) from error
            if normalized != entry:
                papers[paper_id] = normalized
                repaired += 1
    write_json(filename, data)
    logging.info("Repaired %s entries in %s", repaired, filename)
    return repaired


def run(config, repair_existing_data=False):
    json_path = config['json_path']
    if repair_existing_data:
        repair_paper_entries(json_path)
        return
    updates = []
    for topic, query in config['queries'].items():
        updates.append(get_daily_papers(
            topic,
            query,
            config['max_results'],
            config.get('max_pages', 5),
        ))
    update_json_file(json_path, updates)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--config_path', default='config.yaml')
    parser.add_argument('--repair_existing_data', action='store_true')
    args = parser.parse_args()
    run(
        load_config(args.config_path),
        repair_existing_data=args.repair_existing_data,
    )
