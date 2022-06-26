from boto_basics import BotoBasics
from names import Names

basics = BotoBasics()


def main():
    names = Names("")

    for log_group in basics.list_log_groups(prefix=names.log_group):
        name = log_group["logGroupName"]
        basics.delete_log_group(name)
        print(f"Deleted log group {name}")

    for bucket in basics.list_buckets():
        if bucket.name.startswith(names.bucket):
            basics.delete_bucket(bucket)
            print(f"Deleted bucket {bucket.name}")

    for table in basics.list_tables():
        if table.table_name.startswith(names.dynamodb):
            basics.delete_table(table)
            print(f"Deleted table {table.table_name}")


if __name__ == "__main__":
    main()
