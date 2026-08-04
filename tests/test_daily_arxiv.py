import datetime
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "daily_arxiv.py"
WEB_PAGE_PATH = PROJECT_ROOT / "docs" / "papers-json.html"
CONFIG_PATH = PROJECT_ROOT / "config.yaml"
DAILY_WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "cv-arxiv-daily.yml"
WEEKLY_WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "update_paper_links.yml"


def evaluate_page_script(expression):
    node = shutil.which("node")
    if node is None:
        raise AssertionError("Node.js is required for frontend regression tests")

    harness = r"""
const fs = require('fs');
const vm = require('vm');
const page = fs.readFileSync(process.argv[1], 'utf8');
const scriptMatch = page.match(/<script>([\s\S]*?)<\/script>/);
if (!scriptMatch) throw new Error('Page script not found');
const sandbox = {
    URL,
    console,
    window: { open() {} },
    document: { addEventListener() {} },
};
vm.createContext(sandbox);
vm.runInContext(scriptMatch[1], sandbox);
const result = vm.runInContext(process.argv[2], sandbox);
process.stdout.write(JSON.stringify(result));
"""
    completed = subprocess.run(
        [node, "-e", harness, str(WEB_PAGE_PATH), expression],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"Page JavaScript failed with exit code {completed.returncode}:\n"
            f"{completed.stderr}"
        )
    return json.loads(completed.stdout)


def load_module():
    # Unit tests use fakes for arXiv and do not require installed packages.
    for dependency in ("arxiv", "yaml"):
        sys.modules.setdefault(dependency, types.ModuleType(dependency))
    spec = importlib.util.spec_from_file_location("daily_arxiv_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


daily_arxiv = load_module()


class FakeSearch:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakeResult:
    def __init__(self, paper_id):
        self.paper_id = paper_id
        self.updated = datetime.datetime(2026, 8, 4)
        self.title = f"Paper {paper_id}"
        self.authors = ["Ada Lovelace"]

    def get_short_id(self):
        return self.paper_id


class FakeClient:
    def __init__(self, results):
        self.available_results = results
        self.searches = []

    def results(self, search, *args, **kwargs):
        self.searches.append((search, args, kwargs))
        return iter(self.available_results)


class PaperEntryTests(unittest.TestCase):
    def test_normalization_repairs_corrupted_historical_entry(self):
        corrupted = (
            "**2025-08-01**\t**Example Paper**\tJane Doe et.al. et.al.\t"
            "[2508.00427)](2508.00427))\tnull\n"
        )

        repaired = daily_arxiv.normalize_paper_entry(corrupted, "2508.00427")

        self.assertEqual(
            repaired,
            "**2025-08-01**\t**Example Paper**\tJane Doe et.al.\t"
            "[2508.00427](https://arxiv.org/pdf/2508.00427.pdf)\n",
        )

    def test_normalization_removes_legacy_code_link(self):
        entry = (
            "**2026-08-02**\t**A Paper**\tAda Lovelace et.al.\t"
            "[2608.01053](http://arxiv.org/pdf/2608.01053.pdf)\t"
            "**[link](https://github.com/example/project)**\n"
        )

        normalized = daily_arxiv.normalize_paper_entry(entry, "2608.01053")

        self.assertNotIn("github.com", normalized)
        self.assertNotIn("\tnull", normalized)
        self.assertIn("https://arxiv.org/pdf/2608.01053.pdf", normalized)
        self.assertEqual(normalized.count("et.al."), 1)

    def test_normalization_preserves_pipe_delimited_legacy_fields(self):
        entry = (
            "| **2024-01-02** | **Legacy A* Paper** | Ada Lovelace et.al. | "
            "[2401.00001](http://arxiv.org/pdf/2401.00001.pdf) | null |"
        )

        normalized = daily_arxiv.normalize_paper_entry(entry, "2401.00001")

        self.assertEqual(
            normalized,
            "**2024-01-02**\t**Legacy A* Paper**\tAda Lovelace et.al.\t"
            "[2401.00001](https://arxiv.org/pdf/2401.00001.pdf)\n",
        )

    def test_repair_rejects_unparseable_entries_without_replacing_file(self):
        original = {"3D": {"2401.00001": "damaged entry without fields"}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "papers.json"
            original_text = json.dumps(original)
            path.write_text(original_text, encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "2401.00001"):
                daily_arxiv.repair_paper_entries(path)

            self.assertEqual(path.read_text(encoding="utf-8"), original_text)

    def test_repair_paper_entries_makes_no_network_requests(self):
        data = {
            "3D": {
                "2508.00427": (
                    "**2025-08-01**\t**Example Paper**\tJane Doe et.al. et.al.\t"
                    "[2508.00427)](2508.00427))\tnull\n"
                )
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "papers.json"
            path.write_text(json.dumps(data), encoding="utf-8")

            self.assertEqual(daily_arxiv.repair_paper_entries(path), 1)
            repaired = json.loads(path.read_text(encoding="utf-8"))

        entry = repaired["3D"]["2508.00427"]
        self.assertIn("https://arxiv.org/pdf/2508.00427.pdf", entry)
        self.assertNotIn("\tnull", entry)

    def test_update_json_file_preserves_historical_entries(self):
        historical_entry = (
            "**2012-04-09**\t**Historical Paper**\tJane Doe et.al.\t"
            "[2508.00001](https://arxiv.org/pdf/2508.00001.pdf)\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "papers.json"
            path.write_text(json.dumps({"3D": {"2508.00001": historical_entry}}),
                            encoding="utf-8")

            daily_arxiv.update_json_file(path, [
                {"3D": {"2508.00002": "new 3D paper"}},
                {"Diffusion": {"2508.00003": "new diffusion paper"}},
            ])
            merged = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(merged["3D"]["2508.00001"], historical_entry)
        self.assertEqual(merged["3D"]["2508.00002"], "new 3D paper")
        self.assertEqual(merged["Diffusion"]["2508.00003"], "new diffusion paper")

    def test_write_json_keeps_existing_file_when_serialization_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "papers.json"
            original = {"3D": {"2508.00001": "historical paper"}}
            path.write_text(json.dumps(original), encoding="utf-8")

            with self.assertRaises(TypeError):
                daily_arxiv.write_json(path, {"invalid": {"not-json": {1}}})

            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), original)
            self.assertEqual(list(Path(directory).glob(".papers.json.*.tmp")), [])

    def test_build_query_combines_invert_without_an_extra_and(self):
        query = daily_arxiv.build_query({
            "filters": ["diffusion"],
            "categories": ["cat:cs.CV"],
            "invert": ["survey paper"],
        })

        self.assertEqual(query, "(diffusion) AND (cat:cs.CV) ANDNOT (\"survey paper\")")
        with self.assertRaises(ValueError):
            daily_arxiv.build_query({"invert": ["survey paper"]})

    def test_get_daily_papers_requests_the_configured_total_once(self):
        fake_client = FakeClient([FakeResult("2608.00001v2"), FakeResult("2608.00002v1")])
        sort_criterion = types.SimpleNamespace(SubmittedDate="submitted-date")
        with mock.patch.object(daily_arxiv.arxiv, "Client", return_value=fake_client, create=True), \
                mock.patch.object(daily_arxiv.arxiv, "Search", FakeSearch, create=True), \
                mock.patch.object(daily_arxiv.arxiv, "SortCriterion", sort_criterion, create=True):
            papers = daily_arxiv.get_daily_papers("3D", "query", max_results=100, max_pages=5)

        self.assertEqual(len(fake_client.searches), 1)
        search, args, kwargs = fake_client.searches[0]
        self.assertEqual(search.max_results, 500)
        self.assertEqual(args, ())
        self.assertEqual(kwargs, {})
        self.assertEqual(set(papers["3D"]), {"2608.00001", "2608.00002"})
        self.assertNotIn("\tnull", papers["3D"]["2608.00001"])

    def test_web_page_uses_safe_dom_rendering_without_code_links(self):
        page = WEB_PAGE_PATH.read_text(encoding="utf-8")

        self.assertIn("text.replace(/\\n$/, '').split('\\t')", page)
        self.assertIn("getSafeArxivPdfUrl", page)
        self.assertIn("document.createElement", page)
        self.assertIn("openPdf(paper.pdfLink)", page)
        self.assertNotIn("innerHTML", page)
        self.assertNotIn("insertAdjacentHTML", page)
        self.assertNotIn("codeLink", page)
        self.assertNotIn("http://arxiv.org", page)

    def test_web_page_preserves_titles_containing_asterisks(self):
        paper = evaluate_page_script(r"""
(() => parsePaperLine(
    '**2026-08-04**\t**RRT*: Planning with $C^*$-Algebras**\tAda et.al.\t' +
    '[2608.00001](https://arxiv.org/pdf/2608.00001.pdf)\n'
))()
""")

        self.assertEqual(paper["title"], "RRT*: Planning with $C^*$-Algebras")
        self.assertEqual(paper["pdfId"], "2608.00001")

    def test_load_more_slices_the_filtered_result_array(self):
        next_ids = evaluate_page_script(r"""
(() => {
    const filtered = Array.from({length: 150}, (_, index) => ({id: (index + 1) * 2}));
    return getNextPaperBatch(filtered, 100).map(paper => paper.id);
})()
""")
        page = WEB_PAGE_PATH.read_text(encoding="utf-8")

        self.assertEqual(next_ids, list(range(202, 301, 2)))
        self.assertIn("appendLoadMore(container, categoryPapers, visibleCount)", page)
        self.assertNotIn("getSortedCategoryPapers(category).slice(currentCount", page)

    def test_diffusion_query_is_limited_to_computer_vision(self):
        config = CONFIG_PATH.read_text(encoding="utf-8")
        diffusion_block = config.split('"Diffusion":', 1)[1].split('"Robotics":', 1)[0]

        self.assertIn('categories: ["cat:cs.CV"]', diffusion_block)

    def test_papers_with_code_workflow_and_references_are_removed(self):
        source = MODULE_PATH.read_text(encoding="utf-8").lower()
        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8").lower()
        workflow = DAILY_WORKFLOW_PATH.read_text(encoding="utf-8")

        self.assertNotIn("paperswithcode", source)
        self.assertNotIn("import requests", source)
        self.assertNotIn("papers with code", readme)
        self.assertNotIn("update_paper_links", source)
        self.assertFalse(WEEKLY_WORKFLOW_PATH.exists())
        self.assertIn("python -m pip install -r requirements.txt", workflow)
        self.assertIn("python -m unittest discover -s tests -v", workflow)
        self.assertIn("actions/setup-node@v4", workflow)
        self.assertIn("concurrency:", workflow)


if __name__ == "__main__":
    unittest.main()
