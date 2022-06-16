from boto_basics import BotoBasics
from names import RENDER_JOB_PREFIX

basics = BotoBasics()


def main():
    for log_group in basics.list_log_groups(RENDER_JOB_PREFIX):
        name = log_group["logGroupName"]
        basics.delete_log_group(name)
        print(f"Deleted log group {name}")

    for bucket in basics.list_buckets():
        if bucket.name.startswith(RENDER_JOB_PREFIX):
            basics.delete_bucket(bucket)
            print(f"Deleted bucket {bucket.name}")

    for table in basics.list_tables():
        if table.table_name.startswith(RENDER_JOB_PREFIX):
            basics.delete_table(table)
            print(f"Deleted table {table.table_name}")


if __name__ == "__main__":
    main()
