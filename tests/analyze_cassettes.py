import json
from pathlib import Path
import yaml

import gzip
import json


def parse_cassette_binary(binary_content):
    """
    Parse the binary content of a VCR cassette's response body into a dictionary.

    Args:
        binary_content (str or bytes): Binary content of the response body.

    Returns:
        dict: Parsed JSON response.
    """
    # Ensure binary_content is in bytes
    if isinstance(binary_content, str):
        binary_content = binary_content.encode("latin1")

    try:
        # Check if the content is compressed (gzip)
        decoded_content = gzip.decompress(binary_content).decode("utf-8")
    except (OSError, UnicodeDecodeError):
        # If not compressed, assume it's plain JSON
        decoded_content = binary_content.decode("utf-8")

    # Load the JSON content
    response_json = json.loads(decoded_content)
    return response_json


def analyze_cassettes_with_tokens_and_headers(cassettes_dir):
    """
    Analyze VCR cassettes to summarize token usage and header metrics.

    Args:
        cassettes_dir (Path): Path to the directory containing VCR cassettes.

    Returns:
        list[dict]: List of metrics for each cassette, including token usage and processing time.
    """
    metrics = []

    for cassette_file in cassettes_dir.glob("*.yaml"):
        with open(cassette_file, "r") as f:
            cassette_data = yaml.safe_load(f)

        for interaction in cassette_data.get("interactions", []):
            # Extract binary response body
            response_body = (
                interaction.get("response", {}).get("body", {}).get("string", "")
            )
            headers = interaction.get("response", {}).get("headers", {})

            # Parse response content
            if response_body:
                parsed_response = parse_cassette_binary(response_body)
                usage = parsed_response.get("usage", {})
                token_metrics = {
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "total_tokens": usage.get("total_tokens"),
                }
            else:
                token_metrics = {
                    "prompt_tokens": None,
                    "completion_tokens": None,
                    "total_tokens": None,
                }

            # Extract header metrics
            processing_time = headers.get("openai-processing-ms", [None])[0]
            x_request_id = headers.get("x-request-id", [None])[0]

            # Collect data for this interaction
            metrics.append(
                {
                    "file": cassette_file.name,
                    "prompt_tokens": token_metrics["prompt_tokens"],
                    "completion_tokens": token_metrics["completion_tokens"],
                    "total_tokens": token_metrics["total_tokens"],
                    "processing_time_ms": (
                        int(processing_time) if processing_time else None
                    ),
                    "x_request_id": x_request_id,
                }
            )

    return metrics


# Example Usage
CASSETTES_DIR = Path("tests/cassettes")  # Update to your cassettes directory
metrics = analyze_cassettes_with_tokens_and_headers(CASSETTES_DIR)

# Print summary for each cassette
for metric in metrics:
    print(metric)
