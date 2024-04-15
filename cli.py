import argparse


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CLI interface to run specific subscripts in trading program"
    )

    parser.add_argument("-s", "--start", help="Run the main trading program")
    parser.add_argument(
        "-slp",
        "--sell-leftover-positions",
        help="Run the automatic leftover position clearer",
    )
    parser.add_argument(
        "-mo", "--manual-override", help="Manually sell specific stocks on a broker"
    )
    parser.add_argument(
        "-gr",
        "--generate-report",
        help="Generate reports for the day given that all the necessary broker data exists",
    )
    args = parser.parse_args()
    if args.start == "one":
        pass
    elif args.start == "two":
        pass
    else:
        print("Invalid option")


if __name__ == "__main__":
    main()
