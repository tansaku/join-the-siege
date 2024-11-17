import pytest
from werkzeug.datastructures import FileStorage

from src.classifier import classify_file


@pytest.mark.parametrize(
    "filename,expected_classification",
    [
        ("drivers_license_1.jpg", "drivers_licence"),
        ("bank_statement_1.pdf", "bank_statement"),
        ("invoice_1.pdf", "invoice"),
        ("random_document.txt", "unknown file"),
        ("DRIVERS_LICENSE_2.JPG", "drivers_licence"),  # Test case-insensitivity
        ("Bank_Statement_2023.PDF", "bank_statement"),  # Test case-insensitivity
        ("Invoice_final.Pdf", "invoice"),  # Test case-insensitivity
    ],
)
def test_classify_file(filename, expected_classification):
    # Create a mock FileStorage object
    mock_file = FileStorage(filename=filename)

    # Call the classifier
    result = classify_file(mock_file)

    # Assert that the result matches the expected classification
    assert result == expected_classification, f"Failed for filename: {filename}"
