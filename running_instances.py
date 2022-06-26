from boto_basics import BotoBasics, report_non_terminated_instances


# Run to reassure yourself that you don't have any EC2 instances in unexpected states.
def main():
    report_non_terminated_instances(BotoBasics())


if __name__ == "__main__":
    main()
