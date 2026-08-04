# Codebase Bug Fixes Design

The repair keeps the repository's existing tab-separated JSON entry format so
the checked-in data and GitHub Pages frontend remain compatible. The Python
pipeline will gain strict, non-lossy parsing for both the current tab format
and the historical Markdown pipe format. Entries that cannot be parsed with a
date, title, and author will raise an error before the atomic write, preventing
the repair command from silently replacing useful fields with blanks. Normal
updates will merge fetched papers into the existing topic dictionaries without
any date-based pruning. Historical entries are retained indefinitely unless a
future explicit maintenance operation is introduced by the repository owner.

The browser will parse the already-separated fields instead of rediscovering
the title with a regular expression. This preserves titles containing `*`,
including `A*`, `RRT*`, and TeX expressions. Pagination will carry the exact
array currently being displayed into each "Load More" callback. Category
browsing therefore continues paging through the category array, while search
results continue paging through the filtered array without duplicates or
unrelated rows. A small pure batching helper makes this behavior executable in
Node-based regression tests without introducing a browser framework.

The Diffusion query will be restricted to `cs.CV` so new records match the
project's computer-vision scope. Existing out-of-scope history cannot be
classified reliably from the stored fields and is retained instead of being
guessed from titles. GitHub Actions will run the complete unit and JavaScript
regression suite before the network update. Tests cover valid legacy repair,
fail-closed malformed repair,
unlimited historical preservation, starred titles, and filtered pagination.
The workflow remains atomic: failed tests, parsing, fetching, or serialization
leave the published JSON unchanged.
