"""Simple mdbook preprocessor to inject r2p version into the guide.

It will replace:
    - {{#R2P_VERSION_TAG}} with the contents of the R2P_VERSION_TAG environment var
    - {{#R2P_DOCS_URL}} with the configured location of r2p API docs
    - {{#R2P_CRATE_VERSION}} with a relevant toml snippet (e.g. 'version = "0.13.2"')


Tested against mdbook 0.5.0.
"""

import json
import os
import sys

# Set R2P_VERSION in CI to build the correct version into links
R2P_VERSION_TAG = os.environ.get("R2P_VERSION_TAG", "main")

if R2P_VERSION_TAG == "main":
    R2P_DOCS_URL = os.environ.get("R2P_DOCS_URL", "/main/doc")
    R2P_DOCS_VERSION = "latest"
    R2P_CRATE_VERSION = 'git = "https://github.com/jelven007/r2p"'
else:
    # v0.13.2 -> 0.13.2
    version = R2P_VERSION_TAG.lstrip("v")
    R2P_DOCS_URL = os.environ.get("R2P_DOCS_URL", f"/v{version}/doc")
    R2P_DOCS_VERSION = version
    R2P_CRATE_VERSION = f'version = "{version}"'


def replace_item_content(item):
    if not isinstance(item, dict) or "Chapter" not in item:
        return

    # Replace raw and url-encoded forms
    item["Chapter"]["content"] = (
        item["Chapter"]["content"]
        .replace("{{#R2P_VERSION_TAG}}", R2P_VERSION_TAG)
        .replace("{{#R2P_DOCS_URL}}", R2P_DOCS_URL)
        .replace("{{#R2P_DOCS_VERSION}}", R2P_DOCS_VERSION)
        .replace("{{#R2P_CRATE_VERSION}}", R2P_CRATE_VERSION)
    )

    for sub_item in item["Chapter"]["sub_items"]:
        replace_item_content(sub_item)


for line in sys.stdin:
    if line:
        [context, book] = json.loads(line)
        for item in book["items"]:
            replace_item_content(item)
        json.dump(book, fp=sys.stdout)
