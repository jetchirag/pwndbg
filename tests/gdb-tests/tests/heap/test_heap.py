from __future__ import annotations

import re

import gdb
import pytest

import pwndbg
import pwndbg.aglib.heap
import pwndbg.aglib.memory
import pwndbg.aglib.typeinfo
import pwndbg.gdblib.symbol
import tests
from pwndbg.aglib.heap.ptmalloc import SymbolUnresolvableError

HEAP_MALLOC_CHUNK = tests.binaries.get("heap_malloc_chunk.out")
HEAP_MALLOC_CHUNK_DUMP = tests.binaries.get("heap_malloc_chunk_dump.out")


def generate_expected_malloc_chunk_output(chunks):
    expected = {}

    size = int(
        chunks["allocated"][
            (
                "mchunk_size"
                if "mchunk_size" in (f.name for f in chunks["allocated"].type.fields())
                else "size"
            )
        ]
    )
    real_size = size & (0xFFFFFFFFFFFFFFF - 0b111)
    expected["allocated"] = [
        "Allocated chunk | PREV_INUSE",
        f"Addr: {int(chunks['allocated'].address):#x}",
        f"Size: 0x{real_size:02x} (with flag bits: 0x{size:02x})",
        "",
    ]

    size = int(
        chunks["tcache"][
            (
                "mchunk_size"
                if "mchunk_size" in (f.name for f in chunks["tcache"].type.fields())
                else "size"
            )
        ]
    )
    real_size = size & (0xFFFFFFFFFFFFFFF - 0b111)
    expected["tcache"] = [
        f"Free chunk ({'tcachebins' if pwndbg.aglib.heap.current.has_tcache else 'fastbins'}) | PREV_INUSE",
        f"Addr: {int(chunks['tcache'].address):#x}",
        f"Size: 0x{real_size:02x} (with flag bits: 0x{size:02x})",
        f"fd: 0x{int(chunks['tcache']['fd']):02x}",
        "",
    ]

    size = int(
        chunks["fast"][
            (
                "mchunk_size"
                if "mchunk_size" in (f.name for f in chunks["fast"].type.fields())
                else "size"
            )
        ]
    )
    real_size = size & (0xFFFFFFFFFFFFFFF - 0b111)
    expected["fast"] = [
        "Free chunk (fastbins) | PREV_INUSE",
        f"Addr: {int(chunks['fast'].address):#x}",
        f"Size: 0x{real_size:02x} (with flag bits: 0x{size:02x})",
        f"fd: 0x{int(chunks['fast']['fd']):02x}",
        "",
    ]

    size = int(
        chunks["small"][
            (
                "mchunk_size"
                if "mchunk_size" in (f.name for f in chunks["small"].type.fields())
                else "size"
            )
        ]
    )
    real_size = size & (0xFFFFFFFFFFFFFFF - 0b111)
    expected["small"] = [
        "Free chunk (smallbins) | PREV_INUSE",
        f"Addr: {int(chunks['small'].address):#x}",
        f"Size: 0x{real_size:02x} (with flag bits: 0x{size:02x})",
        f"fd: 0x{int(chunks['small']['fd']):02x}",
        f"bk: 0x{int(chunks['small']['bk']):02x}",
        "",
    ]

    size = int(
        chunks["large"][
            (
                "mchunk_size"
                if "mchunk_size" in (f.name for f in chunks["large"].type.fields())
                else "size"
            )
        ]
    )
    real_size = size & (0xFFFFFFFFFFFFFFF - 0b111)
    expected["large"] = [
        "Free chunk (largebins) | PREV_INUSE",
        f"Addr: {int(chunks['large'].address):#x}",
        f"Size: 0x{real_size:02x} (with flag bits: 0x{size:02x})",
        f"fd: 0x{int(chunks['large']['fd']):02x}",
        f"bk: 0x{int(chunks['large']['bk']):02x}",
        f"fd_nextsize: 0x{int(chunks['large']['fd_nextsize']):02x}",
        f"bk_nextsize: 0x{int(chunks['large']['bk_nextsize']):02x}",
        "",
    ]

    size = int(
        chunks["unsorted"][
            (
                "mchunk_size"
                if "mchunk_size" in (f.name for f in chunks["unsorted"].type.fields())
                else "size"
            )
        ]
    )
    real_size = size & (0xFFFFFFFFFFFFFFF - 0b111)
    expected["unsorted"] = [
        "Free chunk (unsortedbin) | PREV_INUSE",
        f"Addr: {int(chunks['unsorted'].address):#x}",
        f"Size: 0x{real_size:02x} (with flag bits: 0x{size:02x})",
        f"fd: 0x{int(chunks['unsorted']['fd']):02x}",
        f"bk: 0x{int(chunks['unsorted']['bk']):02x}",
        "",
    ]

    return expected


def test_malloc_chunk_command(start_binary):
    start_binary(HEAP_MALLOC_CHUNK)
    gdb.execute("break break_here")
    gdb.execute("continue")

    chunks = {}
    results = {}
    chunk_types = ["allocated", "tcache", "fast", "small", "large", "unsorted"]
    for name in chunk_types:
        chunks[name] = pwndbg.aglib.memory.get_typed_pointer_value(
            pwndbg.aglib.heap.current.malloc_chunk,
            int(gdb.lookup_symbol(f"{name}_chunk")[0].value()),
        )
        results[name] = gdb.execute(f"malloc_chunk {name}_chunk", to_string=True).splitlines()

    expected = generate_expected_malloc_chunk_output(chunks)

    for name in chunk_types:
        assert results[name] == expected[name]

    gdb.execute("continue")

    # Print main thread's chunk from another thread
    assert gdb.selected_thread().num == 2
    results["large"] = gdb.execute("malloc_chunk large_chunk", to_string=True).splitlines()
    expected = generate_expected_malloc_chunk_output(chunks)
    assert results["large"] == expected["large"]

    gdb.execute("continue")

    # Test some non-main-arena chunks
    for name in chunk_types:
        chunks[name] = pwndbg.aglib.memory.get_typed_pointer_value(
            pwndbg.aglib.heap.current.malloc_chunk,
            int(gdb.lookup_symbol(f"{name}_chunk")[0].value()),
        )
        results[name] = gdb.execute(f"malloc_chunk {name}_chunk", to_string=True).splitlines()

    expected = generate_expected_malloc_chunk_output(chunks)
    expected["allocated"][0] += " | NON_MAIN_ARENA"
    expected["tcache"][0] += " | NON_MAIN_ARENA"
    expected["fast"][0] += " | NON_MAIN_ARENA"

    for name in chunk_types:
        assert results[name] == expected[name]

    # Print another thread's chunk from the main thread
    gdb.execute("thread 1")
    assert gdb.selected_thread().num == 1
    results["large"] = gdb.execute("malloc_chunk large_chunk", to_string=True).splitlines()
    assert results["large"] == expected["large"]


def test_malloc_chunk_command_heuristic(start_binary):
    start_binary(HEAP_MALLOC_CHUNK)
    gdb.execute("set resolve-heap-via-heuristic force")
    gdb.execute("break break_here")
    gdb.execute("continue")

    chunks = {}
    results = {}
    chunk_types = ["allocated", "tcache", "fast", "small", "large", "unsorted"]
    for name in chunk_types:
        chunks[name] = pwndbg.aglib.heap.current.malloc_chunk(
            int(gdb.lookup_symbol(f"{name}_chunk")[0].value())
        )
        results[name] = gdb.execute(f"malloc_chunk {name}_chunk", to_string=True).splitlines()

    expected = generate_expected_malloc_chunk_output(chunks)

    for name in chunk_types:
        assert results[name] == expected[name]

    gdb.execute("continue")

    # Print main thread's chunk from another thread
    assert gdb.selected_thread().num == 2
    results["large"] = gdb.execute("malloc_chunk large_chunk", to_string=True).splitlines()
    expected = generate_expected_malloc_chunk_output(chunks)
    assert results["large"] == expected["large"]

    gdb.execute("continue")

    # Test some non-main-arena chunks
    for name in chunk_types:
        chunks[name] = pwndbg.aglib.heap.current.malloc_chunk(
            int(gdb.lookup_symbol(f"{name}_chunk")[0].value())
        )
        results[name] = gdb.execute(f"malloc_chunk {name}_chunk", to_string=True).splitlines()

    expected = generate_expected_malloc_chunk_output(chunks)
    expected["allocated"][0] += " | NON_MAIN_ARENA"
    expected["tcache"][0] += " | NON_MAIN_ARENA"
    expected["fast"][0] += " | NON_MAIN_ARENA"

    for name in chunk_types:
        assert results[name] == expected[name]

    # Print another thread's chunk from the main thread
    gdb.execute("thread 1")
    assert gdb.selected_thread().num == 1
    results["large"] = gdb.execute("malloc_chunk large_chunk", to_string=True).splitlines()
    assert results["large"] == expected["large"]


def test_malloc_chunk_dump_command(start_binary):
    start_binary(HEAP_MALLOC_CHUNK_DUMP)
    gdb.execute("break break_here")
    gdb.execute("continue")

    chunk = pwndbg.aglib.memory.get_typed_pointer_value(
        pwndbg.aglib.heap.current.malloc_chunk, int(gdb.lookup_symbol("test_chunk")[0].value())
    )
    chunk_addr = chunk.address

    malloc_chunk = gdb.execute(f"malloc_chunk {int(chunk_addr):#x} -d", to_string=True)

    size = int(
        chunk[("mchunk_size" if "mchunk_size" in (f.name for f in chunk.type.fields()) else "size")]
    )

    real_size = size & (0xFFFFFFFFFFFFFFF - 0b111)

    chunk_addr = int(chunk.address)
    expected = [
        "Allocated chunk | PREV_INUSE",
        f"Addr: 0x{chunk_addr:x}",
        f"Size: 0x{real_size:02x} (with flag bits: 0x{size:02x})",
        "",
        "hexdump",
        f"+0000 0x{chunk_addr:x}  00 00 00 00 00 00 00 00  31 00 00 00 00 00 00 00  │........│1.......│",
        f"+0010 0x{chunk_addr+0x10:x}  54 68 69 73 20 69 73 20  61 20 74 65 73 74 20 73  │This.is.│a.test.s│",
        f"+0020 0x{chunk_addr+0x20:x}  74 72 69 6e 67 00 00 00  00 00 00 00 00 00 00 00  │tring...│........│",
        f"+0030 0x{chunk_addr+0x30:x}  00 00 00 00 00 00 00 00                           │........│        │",
    ]

    # now just compare the output
    assert malloc_chunk.splitlines() == expected


class mock_for_heuristic:
    def __init__(self, mock_symbols=[], mock_all=False):
        self.mock_symbols = (
            mock_symbols  # every symbol's address in the list will be mocked to `None`
        )
        self.mock_all = mock_all  # all symbols will be mocked to `None`
        # Save `pwndbg.gdblib.symbol.address` and `pwndbg.gdblib.symbol.static_linkage_symbol_address` before mocking
        self.saved_address_func = pwndbg.gdblib.symbol.address
        self.saved_static_linkage_symbol_address_func = (
            pwndbg.gdblib.symbol.static_linkage_symbol_address
        )

    def __enter__(self):
        def mock(original):
            def _mock(symbol, *args, **kwargs):
                if self.mock_all:
                    return None
                for s in self.mock_symbols:
                    if s == symbol:
                        return None
                return original(symbol, *args, **kwargs)

            return _mock

        # Mock `pwndbg.gdblib.symbol.address` and `pwndbg.gdblib.symbol.static_linkage_symbol_address`
        pwndbg.gdblib.symbol.address = mock(pwndbg.gdblib.symbol.address)
        pwndbg.gdblib.symbol.static_linkage_symbol_address = mock(
            pwndbg.gdblib.symbol.static_linkage_symbol_address
        )

    def __exit__(self, exc_type, exc_value, traceback):
        # Restore `pwndbg.gdblib.symbol.address` and `pwndbg.gdblib.symbol.static_linkage_symbol_address`
        pwndbg.gdblib.symbol.address = self.saved_address_func
        pwndbg.gdblib.symbol.static_linkage_symbol_address = (
            self.saved_static_linkage_symbol_address_func
        )


def test_main_arena_heuristic(start_binary):
    start_binary(HEAP_MALLOC_CHUNK)
    gdb.execute("set resolve-heap-via-heuristic force")
    gdb.execute("break break_here")
    gdb.execute("continue")

    # Use the debug symbol to get the address of `main_arena`
    main_arena_addr_via_debug_symbol = pwndbg.gdblib.symbol.static_linkage_symbol_address(
        "main_arena"
    ) or pwndbg.gdblib.symbol.address("main_arena")

    # Check if we can get the address of `main_arena` from debug symbols and the struct of `main_arena` is correct
    assert pwndbg.aglib.heap.current.main_arena is not None
    # Check the address of `main_arena` is correct
    assert pwndbg.aglib.heap.current.main_arena.address == main_arena_addr_via_debug_symbol
    # Check the struct size is correct
    assert (
        pwndbg.aglib.heap.current.main_arena._gdbValue.type.sizeof
        == pwndbg.aglib.typeinfo.lookup_types("struct malloc_state").sizeof
    )
    pwndbg.aglib.heap.current = type(pwndbg.aglib.heap.current)()  # Reset the heap object of pwndbg

    # Check if we can get the address of `main_arena` by parsing the .data section of the ELF of libc
    with mock_for_heuristic(["main_arena"]):
        assert pwndbg.aglib.heap.current.main_arena is not None
        # Check the address of `main_arena` is correct
        assert pwndbg.aglib.heap.current.main_arena.address == main_arena_addr_via_debug_symbol


def test_mp_heuristic(start_binary):
    start_binary(HEAP_MALLOC_CHUNK)
    gdb.execute("set resolve-heap-via-heuristic force")
    gdb.execute("break break_here")
    gdb.execute("continue")

    # Use the debug symbol to get the address of `mp_`
    mp_addr_via_debug_symbol = pwndbg.gdblib.symbol.static_linkage_symbol_address(
        "mp_"
    ) or pwndbg.gdblib.symbol.address("mp_")

    # Check if we can get the address of `mp_` from debug symbols and the struct of `mp_` is correct
    assert pwndbg.aglib.heap.current.mp is not None
    # Check the address of `main_arena` is correct
    assert pwndbg.aglib.heap.current.mp.address == mp_addr_via_debug_symbol
    # Check the struct size is correct
    assert (
        pwndbg.aglib.heap.current.mp.type.sizeof
        == pwndbg.aglib.typeinfo.lookup_types("struct malloc_par").sizeof
    )
    pwndbg.aglib.heap.current = type(pwndbg.aglib.heap.current)()  # Reset the heap object of pwndbg

    # Check if we can get the address of `mp_` by parsing the .data section of the ELF of libc
    with mock_for_heuristic(["mp_"]):
        assert pwndbg.aglib.heap.current.mp is not None
        # Check the address of `mp_` is correct
        assert pwndbg.aglib.heap.current.mp.address == mp_addr_via_debug_symbol


@pytest.mark.parametrize(
    "is_multi_threaded", [False, True], ids=["single-threaded", "multi-threaded"]
)
def test_thread_cache_heuristic(start_binary, is_multi_threaded):
    # TODO: Support other architectures or different libc versions
    start_binary(HEAP_MALLOC_CHUNK)
    gdb.execute("set resolve-heap-via-heuristic force")
    gdb.execute("break break_here")
    gdb.execute("continue")
    if is_multi_threaded:
        gdb.execute("continue")
        assert gdb.selected_thread().num == 2

    # Use the debug symbol to find the address of `thread_cache`
    tcache_addr_via_debug_symbol = pwndbg.gdblib.symbol.static_linkage_symbol_address(
        "tcache"
    ) or pwndbg.gdblib.symbol.address("tcache")
    thread_cache_addr_via_debug_symbol = pwndbg.aglib.memory.u(tcache_addr_via_debug_symbol)

    # Check if we can get the address of `thread_cache` from debug symbols and the struct of `thread_cache` is correct
    assert pwndbg.aglib.heap.current.thread_cache is not None
    # Check the address of `thread_cache` is correct
    assert pwndbg.aglib.heap.current.thread_cache.address == thread_cache_addr_via_debug_symbol
    # Check the struct size is correct
    assert (
        pwndbg.aglib.heap.current.thread_cache.type.sizeof
        == pwndbg.aglib.typeinfo.lookup_types("struct tcache_perthread_struct").sizeof
    )
    pwndbg.aglib.heap.current = type(pwndbg.aglib.heap.current)()  # Reset the heap object of pwndbg

    # Check if we can get the address of `tcache` by using the first chunk or by brute force
    with mock_for_heuristic(["tcache"]):
        # Check if we can find tcache by brute force
        pwndbg.aglib.heap.current.prompt_for_brute_force_thread_cache_permission = lambda: True
        assert pwndbg.aglib.heap.current.thread_cache.address == thread_cache_addr_via_debug_symbol
        pwndbg.aglib.heap.current = type(
            pwndbg.aglib.heap.current
        )()  # Reset the heap object of pwndbg
        # Check if we can find tcache by using the first chunk
        # # Note: This will NOT work when can NOT find the heap boundaries or the the arena is been shared
        pwndbg.aglib.heap.current.prompt_for_brute_force_thread_cache_permission = lambda: False
        assert pwndbg.aglib.heap.current.thread_cache.address == thread_cache_addr_via_debug_symbol


@pytest.mark.parametrize(
    "is_multi_threaded", [False, True], ids=["single-threaded", "multi-threaded"]
)
def test_thread_arena_heuristic(start_binary, is_multi_threaded):
    # TODO: Support other architectures or different libc versions
    start_binary(HEAP_MALLOC_CHUNK)
    gdb.execute("set resolve-heap-via-heuristic force")
    gdb.execute("break break_here")
    gdb.execute("continue")
    if is_multi_threaded:
        gdb.execute("continue")
        assert gdb.selected_thread().num == 2

    # Use the debug symbol to find the value of `thread_arena`
    thread_arena_via_debug_symbol = pwndbg.gdblib.symbol.static_linkage_symbol_address(
        "thread_arena"
    ) or pwndbg.gdblib.symbol.address("thread_arena")
    assert thread_arena_via_debug_symbol is not None
    thread_arena_via_debug_symbol = pwndbg.aglib.memory.u(thread_arena_via_debug_symbol)
    assert thread_arena_via_debug_symbol > 0

    # Check if we can get the address of `thread_arena` from debug symbols and the value of `thread_arena` is correct
    assert pwndbg.aglib.heap.current.thread_arena is not None
    # Check the address of `thread_arena` is correct
    assert pwndbg.aglib.heap.current.thread_arena.address == thread_arena_via_debug_symbol
    pwndbg.aglib.heap.current = type(pwndbg.aglib.heap.current)()  # Reset the heap object of pwndbg

    # Check if we can use brute-force to find the `thread_arena` when multi-threaded, and if we can use the `main_arena` as the `thread_arena` when single-threaded
    with mock_for_heuristic(["thread_arena"]):
        # mock the prompt to avoid input
        pwndbg.aglib.heap.current.prompt_for_brute_force_thread_arena_permission = lambda: True
        assert pwndbg.aglib.heap.current.thread_arena is not None
        # Check the value of `thread_arena` is correct
        assert pwndbg.aglib.heap.current.thread_arena.address == thread_arena_via_debug_symbol


def test_global_max_fast_heuristic(start_binary):
    # TODO: Support other architectures or different libc versions
    start_binary(HEAP_MALLOC_CHUNK)
    gdb.execute("set resolve-heap-via-heuristic force")
    gdb.execute("break break_here")
    gdb.execute("continue")

    # Use the debug symbol to find the address of `global_max_fast`
    global_max_fast_addr_via_debug_symbol = pwndbg.gdblib.symbol.static_linkage_symbol_address(
        "global_max_fast"
    ) or pwndbg.gdblib.symbol.address("global_max_fast")
    assert global_max_fast_addr_via_debug_symbol is not None

    # Check if we can get the address of `global_max_fast` from debug symbols and the value of `global_max_fast` is correct
    assert pwndbg.aglib.heap.current.global_max_fast is not None
    # Check the address of `global_max_fast` is correct
    assert pwndbg.aglib.heap.current._global_max_fast_addr == global_max_fast_addr_via_debug_symbol
    pwndbg.aglib.heap.current = type(pwndbg.aglib.heap.current)()  # Reset the heap object of pwndbg

    # Check if we can return the default value even if we can NOT find the address of `global_max_fast`
    with mock_for_heuristic(["global_max_fast"]):
        assert pwndbg.aglib.heap.current.global_max_fast == pwndbg.aglib.memory.u(
            global_max_fast_addr_via_debug_symbol
        )


@pytest.mark.parametrize(
    "is_multi_threaded", [False, True], ids=["single-threaded", "multi-threaded"]
)
def test_heuristic_fail_gracefully(start_binary, is_multi_threaded):
    # TODO: Support other architectures or different libc versions
    start_binary(HEAP_MALLOC_CHUNK)
    gdb.execute("set resolve-heap-via-heuristic force")
    gdb.execute("break break_here")
    gdb.execute("continue")
    if is_multi_threaded:
        gdb.execute("continue")
        assert gdb.selected_thread().num == 2

    def _test_heuristic_fail_gracefully(name):
        try:
            getattr(pwndbg.aglib.heap.current, name)
        except SymbolUnresolvableError as e:
            # That's the only exception we expect
            assert e.symbol  # we should show what symbol we failed to resolve

    # Mock all address and mess up the memory
    with mock_for_heuristic(mock_all=True):
        # mock the prompt to avoid input
        pwndbg.aglib.heap.current.prompt_for_brute_force_thread_arena_permission = lambda: False
        pwndbg.aglib.heap.current.prompt_for_brute_force_thread_cache_permission = lambda: False
        _test_heuristic_fail_gracefully("main_arena")
        _test_heuristic_fail_gracefully("mp")
        _test_heuristic_fail_gracefully("global_max_fast")
        _test_heuristic_fail_gracefully("thread_cache")
        _test_heuristic_fail_gracefully("thread_arena")


##
# Jemalloc Tests
##
HEAP_JEMALLOC_EXTENT_INFO = tests.binaries.get("heap_jemalloc_extent_info.out")
HEAP_JEMALLOC_HEAP = tests.binaries.get("heap_jemalloc_heap.out")
re_match_valid_address = r"0x7ffff[0-9a-fA-F]{6,9}"


def test_jemalloc_find_extent(start_binary):
    start_binary(HEAP_JEMALLOC_EXTENT_INFO)
    gdb.execute("break break_here")
    gdb.execute("continue")

    # run jemalloc extent_info command
    result = gdb.execute("jemalloc_find_extent ptr", to_string=True).splitlines()

    expected_output = [
        "Jemalloc find extent",
        "This command was tested only for jemalloc 5.3.0 and does not support lower versions",
        "",
        r"Pointer Address: " + re_match_valid_address,
        r"Extent Address: " + re_match_valid_address,
        "",
        r"Allocated Address: " + re_match_valid_address,
        r"Extent Address: " + re_match_valid_address,
        "Size: 0x1000",
        "Small class: True",
    ]

    for i in range(len(expected_output)):
        assert re.match(expected_output[i], result[i])


def test_jemalloc_extent_info(start_binary):
    start_binary(HEAP_JEMALLOC_EXTENT_INFO)
    gdb.execute("break break_here")
    gdb.execute("continue")

    EXPECTED_EXTENT_ADDRESS = 0x7FFFF7A16580

    # run jemalloc extent_info command
    result = gdb.execute(
        f"jemalloc_extent_info {EXPECTED_EXTENT_ADDRESS}", to_string=True
    ).splitlines()

    expected_output = [
        "Jemalloc extent info",
        "This command was tested only for jemalloc 5.3.0 and does not support lower versions",
        "",
        r"Allocated Address: " + re_match_valid_address,
        r"Extent Address: " + re_match_valid_address,
        "Size: 0x1000",
        "Small class: True",
    ]

    for i in range(len(expected_output)):
        assert re.match(expected_output[i], result[i])


@pytest.mark.skip(reason="Output is resulting in duplicate extents")
def test_jemalloc_heap(start_binary):
    start_binary(HEAP_JEMALLOC_HEAP)
    gdb.execute("break break_here")
    gdb.execute("continue")

    # run jemalloc extent_info command
    result = gdb.execute("jemalloc_heap", to_string=True).splitlines()

    expected_output = [
        "Jemalloc heap",
        "This command was tested only for jemalloc 5.3.0 and does not support lower versions",
    ]

    expected_output += [
        "",
        "Allocated Address: " + re_match_valid_address,
        r"Extent Address: " + re_match_valid_address,
        "Size: 0x401000",
        "Small class: False",
    ]

    expected_output += [
        "",
        "Allocated Address: " + re_match_valid_address,
        r"Extent Address: " + re_match_valid_address,
        "Size: 0x8000",
        "Small class: False",
    ]

    expected_output += [
        "",
        "Allocated Address: " + re_match_valid_address,
        r"Extent Address: " + re_match_valid_address,
        "Size: 0x8000",
        "Small class: False",
    ]

    expected_output += [
        "",
        "Allocated Address: " + re_match_valid_address,
        r"Extent Address: " + re_match_valid_address,
        "Size: 0x1f7000",
        "Small class: False",
    ]

    for i in range(len(expected_output)):
        assert re.match(expected_output[i], result[i])
