from threading import Barrier, Thread

import pytest

from deltalake import DeltaTable


def test_read_simple_table_to_dict():
    table_path = "../rust/tests/data/simple_table"
    dt = DeltaTable(table_path)
    assert dt.to_pyarrow_dataset().to_table().to_pydict() == {"id": [5, 7, 9]}


def test_read_simple_table_by_version_to_dict():
    table_path = "../rust/tests/data/delta-0.2.0"
    dt = DeltaTable(table_path, version=2)
    assert dt.to_pyarrow_dataset().to_table().to_pydict() == {"value": [1, 2, 3]}


def test_get_files_partitioned_table():
    table_path = "../rust/tests/data/delta-0.8.0-partitioned"
    dt = DeltaTable(table_path)
    partition_filters = [("day", "=", "3")]
    assert dt.files_by_partitions(partition_filters=partition_filters) == [
        "year=2020/month=2/day=3/part-00000-94d16827-f2fd-42cd-a060-f67ccc63ced9.c000.snappy.parquet"
    ]
    partition_filters = [("day", "!=", "3")]
    assert dt.files_by_partitions(partition_filters=partition_filters) == [
        "year=2020/month=1/day=1/part-00000-8eafa330-3be9-4a39-ad78-fd13c2027c7e.c000.snappy.parquet",
        "year=2020/month=2/day=5/part-00000-89cdd4c8-2af7-4add-8ea3-3990b2f027b5.c000.snappy.parquet",
        "year=2021/month=12/day=20/part-00000-9275fdf4-3961-4184-baa0-1c8a2bb98104.c000.snappy.parquet",
        "year=2021/month=12/day=4/part-00000-6dc763c0-3e8b-4d52-b19e-1f92af3fbb25.c000.snappy.parquet",
        "year=2021/month=4/day=5/part-00000-c5856301-3439-4032-a6fc-22b7bc92bebb.c000.snappy.parquet",
    ]
    partition_filters = [("day", "in", ["3", "20"])]
    assert dt.files_by_partitions(partition_filters=partition_filters) == [
        "year=2020/month=2/day=3/part-00000-94d16827-f2fd-42cd-a060-f67ccc63ced9.c000.snappy.parquet",
        "year=2021/month=12/day=20/part-00000-9275fdf4-3961-4184-baa0-1c8a2bb98104.c000.snappy.parquet",
    ]
    partition_filters = [("day", "not in", ["3", "20"])]
    assert dt.files_by_partitions(partition_filters=partition_filters) == [
        "year=2020/month=1/day=1/part-00000-8eafa330-3be9-4a39-ad78-fd13c2027c7e.c000.snappy.parquet",
        "year=2020/month=2/day=5/part-00000-89cdd4c8-2af7-4add-8ea3-3990b2f027b5.c000.snappy.parquet",
        "year=2021/month=12/day=4/part-00000-6dc763c0-3e8b-4d52-b19e-1f92af3fbb25.c000.snappy.parquet",
        "year=2021/month=4/day=5/part-00000-c5856301-3439-4032-a6fc-22b7bc92bebb.c000.snappy.parquet",
    ]
    partition_filters = [("day", "not in", ["3", "20"]), ("year", "=", "2021")]
    assert dt.files_by_partitions(partition_filters=partition_filters) == [
        "year=2021/month=12/day=4/part-00000-6dc763c0-3e8b-4d52-b19e-1f92af3fbb25.c000.snappy.parquet",
        "year=2021/month=4/day=5/part-00000-c5856301-3439-4032-a6fc-22b7bc92bebb.c000.snappy.parquet",
    ]
    partition_filters = [("invalid_operation", "=>", "3")]
    with pytest.raises(Exception):
        assert dt.files_by_partitions(partition_filters=partition_filters)
    partition_filters = [("invalid_operation", "=", ["3", "20"])]
    with pytest.raises(Exception):
        assert dt.files_by_partitions(partition_filters=partition_filters)
    partition_filters = [("day", "=", 3)]
    with pytest.raises(Exception):
        assert dt.files_by_partitions(partition_filters=partition_filters)
    # TODO: partition_filters = [("unknown_column", "=", "3")], not accepting unknown partition key


class TestableThread(Thread):
    """Wrapper around `threading.Thread` that propagates exceptions."""

    def __init__(self, target, *args):
        Thread.__init__(self, target=target, *args)
        self.exc = None

    def run(self):
        """Method representing the thread's activity.
        You may override this method in a subclass. The standard run() method
        invokes the callable object passed to the object's constructor as the
        target argument, if any, with sequential and keyword arguments taken
        from the args and kwargs arguments, respectively.
        """
        try:
            Thread.run(self)
        except BaseException as e:
            self.exc = e

    def join(self, timeout=None):
        """Wait until the thread terminates.
        This blocks the calling thread until the thread whose join() method is
        called terminates -- either normally or through an unhandled exception
        or until the optional timeout occurs.
        When the timeout argument is present and not None, it should be a
        floating point number specifying a timeout for the operation in seconds
        (or fractions thereof). As join() always returns None, you must call
        is_alive() after join() to decide whether a timeout happened -- if the
        thread is still alive, the join() call timed out.
        When the timeout argument is not present or None, the operation will
        block until the thread terminates.
        A thread can be join()ed many times.
        join() raises a RuntimeError if an attempt is made to join the current
        thread as that would cause a deadlock. It is also an error to join() a
        thread before it has been started and attempts to do so raises the same
        exception.
        """
        super(TestableThread, self).join(timeout)
        if self.exc:
            raise self.exc


@pytest.mark.timeout(timeout=5, method="thread")
def test_read_multiple_tables_from_s3(s3cred):
    """
    Should be able to create multiple cloud storage based DeltaTable instances
    without blocking on async rust function calls.
    """
    for path in ["s3://deltars/simple", "s3://deltars/simple"]:
        t = DeltaTable(path)
        assert t.files() == [
            "part-00000-c1777d7d-89d9-4790-b38a-6ee7e24456b1-c000.snappy.parquet",
            "part-00001-7891c33d-cedc-47c3-88a6-abcfb049d3b4-c000.snappy.parquet",
            "part-00004-315835fe-fb44-4562-98f6-5e6cfa3ae45d-c000.snappy.parquet",
            "part-00007-3a0e4727-de0d-41b6-81ef-5223cf40f025-c000.snappy.parquet",
            "part-00000-2befed33-c358-4768-a43c-3eda0d2a499d-c000.snappy.parquet",
        ]


@pytest.mark.timeout(timeout=10, method="thread")
def test_read_multiple_tables_from_s3_multi_threaded(s3cred):
    thread_count = 10
    b = Barrier(thread_count, timeout=5)

    # make sure it works within multiple threads as well
    def read_table():
        b.wait()
        t = DeltaTable("s3://deltars/simple")
        assert t.files() == [
            "part-00000-c1777d7d-89d9-4790-b38a-6ee7e24456b1-c000.snappy.parquet",
            "part-00001-7891c33d-cedc-47c3-88a6-abcfb049d3b4-c000.snappy.parquet",
            "part-00004-315835fe-fb44-4562-98f6-5e6cfa3ae45d-c000.snappy.parquet",
            "part-00007-3a0e4727-de0d-41b6-81ef-5223cf40f025-c000.snappy.parquet",
            "part-00000-2befed33-c358-4768-a43c-3eda0d2a499d-c000.snappy.parquet",
        ]

    threads = [TestableThread(target=read_table) for _ in range(thread_count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
