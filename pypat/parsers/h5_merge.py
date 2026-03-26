import sys
from pathlib import Path
from typing import List

import h5py


def merge_h5_files(input_files: List[Path], output_file: Path) -> None:
    with h5py.File(output_file, "w") as h5out:
        for index, file_path in enumerate(input_files):
            with h5py.File(file_path, "r") as h5in:
                group = h5out.create_group(f"sample_{index}")
                for key in h5in:
                    h5in.copy(key, group)


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python -m pypat.parsers.h5_merge output.h5 input1.h5 input2.h5 ...")
        sys.exit(1)

    output = Path(sys.argv[1])
    inputs = [Path(arg) for arg in sys.argv[2:]]
    merge_h5_files(inputs, output)


if __name__ == "__main__":
    main()
