import os
import re
import vcr
import pytest
from src.openai_classifier import query_gpt4

# Directory to store VCR cassettes
CASSETTES_DIR = "tests/cassettes"
os.makedirs(CASSETTES_DIR, exist_ok=True)

# Files to test
FILES_DIR = "files"
TEST_FILES = [
    os.path.join(FILES_DIR, f)
    for f in os.listdir(FILES_DIR)
    if os.path.isfile(os.path.join(FILES_DIR, f))
]

import vcr

# Define the VCR configuration with a before_record hook
vcr_config = vcr.VCR(
    cassette_library_dir="tests/cassettes",
    record_mode="once",
    match_on=["uri", "method"],
    filter_headers=["authorization"],  # Redact the Authorization header
    before_record_request=lambda request: redact_authorization(request),
)


def redact_authorization(request):
    """
    Redact sensitive information (like API keys) from the Authorization header.
    """
    if "Authorization" in request.headers:
        request.headers["Authorization"] = ["Bearer [REDACTED]"]
    return request


def get_classification(file_path):
    """
    Extracts the base name of a file, removing trailing numbers and extensions.

    Args:
        file_path (str): The file path.

    Returns:
        str: The base name without trailing numbers or file extension.
    """
    # Extract the file name without the directory path
    file_name = os.path.basename(file_path)

    # Remove the file extension
    base_name, _ = os.path.splitext(file_name)

    # Remove trailing numbers with an underscore
    base_name = re.sub(r"_\d+$", "", base_name)

    if base_name == "drivers_license":
        return "drivers_licence"

    return base_name


@pytest.mark.parametrize("file_path", TEST_FILES)
def test_classify_file(file_path):
    cassette_path = os.path.join(CASSETTES_DIR, f"{os.path.basename(file_path)}.yaml")

    with vcr.use_cassette(cassette_path, record_mode="once"):
        # Call the real classify_file function
        response = query_gpt4(file_path)

        # Validate the response structure
        assert response.choices[0].message.parsed.document_type == get_classification(
            file_path
        )
