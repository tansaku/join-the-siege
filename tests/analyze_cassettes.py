import gzip
import json
from pathlib import Path
import yaml
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt


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


def analyze_cassettes_with_tokens_and_jpeg_sizes(
    cassettes_dir, output_dir, converted_dir
):
    """
    Analyze VCR cassettes to summarize token usage, processing time, and JPEG file sizes.

    Args:
        cassettes_dir (Path): Path to the directory containing VCR cassettes.
        output_dir (Path): Path to the directory containing the converted JPEGs.

    Returns:
        pd.DataFrame: DataFrame with file metrics and processing data.
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

            # Get size of the corresponding JPEG in the correct directory
            file_name = cassette_file.stem
            if file_name.endswith(".pdf"):
                jpeg_file = converted_dir / cassette_file.stem.replace(".pdf", ".jpg")
            else:
                jpeg_file = output_dir / file_name
            if jpeg_file.exists():
                file_size = jpeg_file.stat().st_size
            else:
                file_size = None

            # Collect data for this interaction
            metrics.append(
                {
                    "file_name": cassette_file.name.replace(".yaml", ""),
                    "jpeg_size_bytes": file_size,
                    "prompt_tokens": token_metrics["prompt_tokens"],
                    "completion_tokens": token_metrics["completion_tokens"],
                    "total_tokens": token_metrics["total_tokens"],
                    "processing_time_ms": (
                        int(processing_time) if processing_time else None
                    ),
                    "x_request_id": x_request_id,
                }
            )

    return pd.DataFrame(metrics)


def plot_relationships_with_consistent_coloring(df):
    """
    Create scatter plots for relationships between JPEG file sizes, tokens, processing time, and costs,
    with consistent colors for each file across all plots and legends in each graph.

    Args:
        df (pd.DataFrame): DataFrame with file metrics.
    """
    # Filter rows with valid JPEG sizes and tokens
    df = df.dropna(
        subset=[
            "jpeg_size_bytes",
            "prompt_tokens",
            "completion_tokens",
            "processing_time_ms",
        ]
    ).copy()

    # Convert JPEG size to kilobytes and tokens to thousands
    df["jpeg_size_kb"] = df["jpeg_size_bytes"] / 1024
    df["total_tokens_thousands"] = df["total_tokens"] / 1000

    # Calculate costs
    df["normal_input_cost"] = df["prompt_tokens"] * 0.150 / 1_000_000
    df["normal_output_cost"] = df["completion_tokens"] * 0.600 / 1_000_000
    df["batch_input_cost"] = df["prompt_tokens"] * 0.075 / 1_000_000
    df["batch_output_cost"] = df["completion_tokens"] * 0.300 / 1_000_000

    # Total normal and batch costs
    df["normal_total_cost"] = df["normal_input_cost"] + df["normal_output_cost"]
    df["batch_total_cost"] = df["batch_input_cost"] + df["batch_output_cost"]

    # Define a consistent color palette based on file names
    unique_files = df["file_name"].unique()
    palette = sns.color_palette("husl", len(unique_files))  # Generate unique colors
    file_colors = dict(zip(unique_files, palette))  # Map file names to colors

    # Set up a 2x2 plot grid
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.subplots_adjust(hspace=0.4, wspace=0.3)

    # Total Tokens vs. JPEG Size
    sns.scatterplot(
        data=df,
        x="jpeg_size_kb",
        y="total_tokens_thousands",
        hue="file_name",
        palette=file_colors,
        ax=axes[0, 0],
        s=100,
    )
    axes[0, 0].set_title("Total Request Tokens vs. JPEG File Size", fontsize=14)
    axes[0, 0].set_xlabel("JPEG File Size (KB)", fontsize=12)
    axes[0, 0].set_ylabel("Total Request Tokens (Thousands)", fontsize=12)
    axes[0, 0].grid(True)

    # Processing Time vs. JPEG Size
    sns.scatterplot(
        data=df,
        x="jpeg_size_kb",
        y="processing_time_ms",
        hue="file_name",
        palette=file_colors,
        ax=axes[0, 1],
        s=100,
    )
    axes[0, 1].set_title("Processing Time vs. JPEG File Size", fontsize=14)
    axes[0, 1].set_xlabel("JPEG File Size (KB)", fontsize=12)
    axes[0, 1].set_ylabel("Processing Time (ms)", fontsize=12)
    axes[0, 1].grid(True)

    # Normal API Cost vs. JPEG Size
    sns.scatterplot(
        data=df,
        x="jpeg_size_kb",
        y="normal_total_cost",
        hue="file_name",
        palette=file_colors,
        ax=axes[1, 0],
        s=100,
    )
    axes[1, 0].set_title("Normal API Cost vs. JPEG File Size", fontsize=14)
    axes[1, 0].set_xlabel("JPEG File Size (KB)", fontsize=12)
    axes[1, 0].set_ylabel("Normal API Cost ($)", fontsize=12)
    axes[1, 0].set_ylim(0, 0.0075)  # Fixed y-axis range
    axes[1, 0].grid(True)

    # Batch API Cost vs. JPEG Size
    sns.scatterplot(
        data=df,
        x="jpeg_size_kb",
        y="batch_total_cost",
        hue="file_name",
        palette=file_colors,
        ax=axes[1, 1],
        s=100,
    )
    axes[1, 1].set_title("Batch API Cost vs. JPEG File Size", fontsize=14)
    axes[1, 1].set_xlabel("JPEG File Size (KB)", fontsize=12)
    axes[1, 1].set_ylabel("Batch API Cost ($)", fontsize=12)
    axes[1, 1].set_ylim(0, 0.0075)  # Fixed y-axis range
    axes[1, 1].grid(True)

    # Show the plots
    plt.show()


# Example Usage
CASSETTES_DIR = Path("tests/cassettes")  # Update to your cassettes directory
OUTPUT_DIR = Path("files")  # Directory with the original files
CONVERTED_DIR = Path("output_images")
df = analyze_cassettes_with_tokens_and_jpeg_sizes(
    CASSETTES_DIR, OUTPUT_DIR, CONVERTED_DIR
)

# Display DataFrame and plot
print(df)
plot_relationships_with_consistent_coloring(df)
