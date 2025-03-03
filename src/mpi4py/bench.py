# Author:  Lisandro Dalcin
# Contact: dalcinl@gmail.com
"""Run MPI benchmarks and tests."""
import os as _os
import sys as _sys


def _prog(cmd=""):
    pyexe = _os.path.basename(_sys.executable)
    return f"{pyexe} -m {__spec__.name} {cmd}".strip()


def helloworld(comm, args=None, verbose=True):
    """Hello, World! using MPI."""
    # pylint: disable=import-outside-toplevel
    from argparse import ArgumentParser
    parser = ArgumentParser(prog=_prog("helloworld"))
    parser.add_argument("-q", "--quiet", action="store_false",
                        dest="verbose", default=verbose,
                        help="quiet output")
    options = parser.parse_args(args)

    from . import MPI
    size = comm.Get_size()
    rank = comm.Get_rank()
    name = MPI.Get_processor_name()
    message = (
        f"Hello, World! I am process "
        f"{rank:{len(str(size - 1))}d} "
        f"of {size} on {name}.\n"
    )
    comm.Barrier()
    if rank > 0:
        comm.Recv([None, 'B'], rank - 1)
    if options.verbose:
        _sys.stdout.write(message)
        _sys.stdout.flush()
    if rank < size - 1:
        comm.Send([None, 'B'], rank + 1)
    comm.Barrier()
    return message


def ringtest(comm, args=None, verbose=True):
    """Time a message going around the ring of processes."""
    # pylint: disable=too-many-locals
    # pylint: disable=too-many-statements
    # pylint: disable=import-outside-toplevel
    from argparse import ArgumentParser
    parser = ArgumentParser(prog=_prog("ringtest"))
    parser.add_argument("-q", "--quiet", action="store_false",
                        dest="verbose", default=verbose,
                        help="quiet output")
    parser.add_argument("-n", "--size", type=int,
                        dest="size", default=1,
                        help="message size")
    parser.add_argument("-s", "--skip", type=int,
                        dest="skip", default=0,
                        help="number of warm-up iterations")
    parser.add_argument("-l", "--loop", type=int,
                        dest="loop", default=1,
                        help="number of iterations")
    options = parser.parse_args(args)

    def ring(comm, n=1, loop=1, skip=0):
        # pylint: disable=invalid-name
        # pylint: disable=missing-docstring
        from array import array
        from . import MPI
        iterations = list(range((loop + skip)))
        size = comm.Get_size()
        rank = comm.Get_rank()
        source = (rank - 1) % size
        dest = (rank + 1) % size
        Sendrecv = comm.Sendrecv
        Send = comm.Send
        Recv = comm.Recv
        Wtime = MPI.Wtime
        sendmsg = array('B', [+42]) * n
        recvmsg = array('B', [0x0]) * n
        if size == 1:
            for i in iterations:
                if i == skip:
                    tic = Wtime()
                Sendrecv(sendmsg, dest, 0,
                         recvmsg, source, 0)
        else:
            if rank == 0:
                for i in iterations:
                    if i == skip:
                        tic = Wtime()
                    Send(sendmsg, dest, 0)
                    Recv(recvmsg, source, 0)
            else:
                sendmsg = recvmsg
                for i in iterations:
                    if i == skip:
                        tic = Wtime()
                    Recv(recvmsg, source, 0)
                    Send(sendmsg, dest, 0)
        toc = Wtime()
        if comm.rank == 0 and sendmsg != recvmsg:  # pragma: no cover
            import warnings
            import traceback
            try:
                warnings.warn("received message does not match!")
            except UserWarning:
                traceback.print_exc()
                comm.Abort(2)
        return toc - tic

    size = getattr(options, 'size', 1)
    loop = getattr(options, 'loop', 1)
    skip = getattr(options, 'skip', 0)
    comm.Barrier()
    elapsed = ring(comm, size, loop, skip)
    if options.verbose and comm.rank == 0:
        _sys.stdout.write(
            f"time for {loop} loops = {elapsed:g} seconds "
            f"({comm.size} processes, {size} bytes)\n"
        )
        _sys.stdout.flush()
    return elapsed


def pingpong(comm, args=None, verbose=True):
    """Time messages between processes."""
    # pylint: disable=too-many-locals
    # pylint: disable=too-many-branches
    # pylint: disable=too-many-statements
    # pylint: disable=import-outside-toplevel
    from argparse import ArgumentParser
    parser = ArgumentParser(prog=_prog("pingpong"))
    parser.add_argument("-q", "--quiet", action="store_false",
                        dest="verbose", default=verbose,
                        help="quiet output")
    parser.add_argument("-m", "--min-size", type=int,
                        dest="min_size", default=1,
                        help="maximum message size")
    parser.add_argument("-n", "--max-size", type=int,
                        dest="max_size", default=1 << 30,
                        help="maximum message size")
    parser.add_argument("-s", "--skip", type=int,
                        dest="skip", default=100,
                        help="number of warm-up iterations")
    parser.add_argument("-l", "--loop", type=int,
                        dest="loop", default=10000,
                        help="number of iterations")
    parser.add_argument("-a", "--array", action="store",
                        dest="array", default="numpy",
                        choices=["numpy", "cupy", "numba", "none"],
                        help="use NumPy/CuPy/Numba arrays")
    parser.add_argument("-p", "--pickle", action="store_true",
                        dest="pickle", default=False,
                        help="use pickle-based send and receive")
    parser.add_argument("--protocol", type=int,
                        dest="protocol", default=None,
                        help="pickle protocol version")
    parser.add_argument("-o", "--outband", action="store_true",
                        dest="outband", default=False,
                        help="use out-of-band pickle-based send and receive")
    parser.add_argument("--threshold", type=int,
                        dest="threshold", default=None,
                        help="size threshold for out-of-band pickle buffers")
    parser.add_argument("--skip-large", type=int,
                        dest="skip_large", default=10)
    parser.add_argument("--loop-large", type=int,
                        dest="loop_large", default=1000)
    parser.add_argument("--large-size", type=int,
                        dest="large_size", default=1 << 14)
    parser.add_argument("--skip-huge", type=int,
                        dest="skip_huge", default=1)
    parser.add_argument("--loop-huge", type=int,
                        dest="loop_huge", default=10)
    parser.add_argument("--huge-size", type=int,
                        dest="huge_size", default=1 << 20)
    parser.add_argument("--no-header", action="store_false",
                        dest="print_header", default=True)
    parser.add_argument("--no-stats", action="store_false",
                        dest="print_stats", default=True)
    options = parser.parse_args(args)

    import statistics
    from . import MPI
    from .util import pkl5

    # pylint: disable=import-error
    numpy = cupy = numba = None
    if options.array == 'numpy':
        try:
            import numpy
        except ImportError:  # pragma: no cover
            pass
    elif options.array == 'cupy':  # pragma: no cover
        import cupy
    elif options.array == 'numba':  # pragma: no cover
        import numba.cuda

    skip = options.skip
    loop = options.loop
    min_size = options.min_size
    max_size = options.max_size
    skip_large = options.skip_large
    loop_large = options.loop_large
    large_size = options.large_size
    skip_huge = options.skip_huge
    loop_huge = options.loop_huge
    huge_size = options.huge_size

    use_pickle = options.pickle or options.outband
    use_outband = options.outband
    protocol = options.protocol if use_pickle else None
    threshold = options.threshold if use_outband else None

    if use_outband:
        comm = pkl5.Intracomm(comm)
    if protocol is not None:
        setattr(MPI.pickle, 'PROTOCOL', protocol)
    if threshold is not None:
        setattr(pkl5.pickle, 'THRESHOLD', threshold)

    buf_sizes = [1 << i for i in range(33)]
    buf_sizes = [n for n in buf_sizes if min_size <= n <= max_size]

    wtime = MPI.Wtime
    if use_pickle:
        send = comm.send
        recv = comm.recv
        sendrecv = comm.sendrecv
    else:
        send = comm.Send
        recv = comm.Recv
        sendrecv = comm.Sendrecv
    s_msg = r_msg = None

    def allocate(nbytes):  # pragma: no cover
        if numpy:
            return numpy.empty(nbytes, 'B')
        elif cupy:
            return cupy.empty(nbytes, 'B')
        elif numba:
            return numba.cuda.device_array(nbytes, 'B')
        else:
            return bytearray(nbytes)

    def run_pingpong():
        rank = comm.Get_rank()
        size = comm.Get_size()
        t_start = wtime()
        if size == 1:
            sendrecv(s_msg, 0, 0, r_msg, 0, 0)
            sendrecv(s_msg, 0, 0, r_msg, 0, 0)
        elif rank == 0:
            send(s_msg, 1, 0)
            recv(r_msg, 1, 0)
        elif rank == 1:
            recv(r_msg, 0, 0)
            send(s_msg, 0, 0)
        t_end = wtime()
        return (t_end - t_start) / 2

    result = []
    for nbytes in buf_sizes:
        if nbytes > large_size:
            skip = min(skip, skip_large)
            loop = min(loop, loop_large)
        if nbytes > huge_size:
            skip = min(skip, skip_huge)
            loop = min(loop, loop_huge)
        iterations = list(range(loop + skip))

        if use_pickle:
            s_msg = allocate(nbytes)
        else:
            s_msg = [allocate(nbytes), nbytes, MPI.BYTE]
            r_msg = [allocate(nbytes), nbytes, MPI.BYTE]

        t_list = []
        comm.Barrier()
        for i in iterations:
            elapsed = run_pingpong()
            if i >= skip:
                t_list.append(elapsed)

        s_msg = r_msg = None

        t_mean = statistics.mean(t_list) if t_list else float('nan')
        t_stdev = statistics.stdev(t_list) if len(t_list) > 1 else 0.0
        result.append((nbytes, t_mean, t_stdev))

        if options.verbose and comm.rank == 0:
            if options.print_header:
                options.print_header = False
                print("# MPI PingPong Test")
                header = "# Size [B]  Bandwidth [MB/s]"
                if options.print_stats:
                    header += " | Time Mean [s] \u00b1 StdDev [s]  Samples"
                print(header, flush=True)
            bandwidth = nbytes / t_mean
            message = f"{nbytes:10d}{bandwidth/1e6:18.2f}"
            if options.print_stats:
                message += f" | {t_mean:.7e} \u00b1 {t_stdev:.4e} {loop:8d}"
            print(message, flush=True)

    return result


def main(args=None):
    """Entry-point for ``python -m mpi4py.bench``."""
    # pylint: disable=import-outside-toplevel
    from argparse import ArgumentParser, REMAINDER
    parser = ArgumentParser(prog=_prog(),
                            usage="%(prog)s [options] <command> [args]")
    parser.add_argument("--threads",
                        action="store_true", dest="threads", default=None,
                        help="initialize MPI with thread support")
    parser.add_argument("--no-threads",
                        action="store_false", dest="threads", default=None,
                        help="initialize MPI without thread support")
    parser.add_argument("--thread-level",
                        dest="thread_level", default=None,
                        action="store", metavar="LEVEL",
                        choices="single funneled serialized multiple".split(),
                        help="initialize MPI with required thread level")
    parser.add_argument("--mpe",
                        action="store_true", dest="mpe", default=False,
                        help="use MPE for MPI profiling")
    parser.add_argument("--vt",
                        action="store_true", dest="vt", default=False,
                        help="use VampirTrace for MPI profiling")
    parser.add_argument("command",
                        action="store", metavar="<command>",
                        help="benchmark command to run")
    parser.add_argument("args",
                        nargs=REMAINDER, metavar="[args]",
                        help="arguments for benchmark command")
    options = parser.parse_args(args)

    from . import rc, profile
    if options.threads is not None:
        rc.threads = options.threads
    if options.thread_level is not None:
        rc.thread_level = options.thread_level
    if options.mpe:
        profile('mpe', logfile='mpi4py')
    if options.vt:
        profile('vt', logfile='mpi4py')

    from . import MPI
    comm = MPI.COMM_WORLD
    if options.command not in main.commands:
        if comm.rank == 0:
            parser.error(f"unknown command '{options.command}'")
        parser.exit(2)
    command = main.commands[options.command]
    command(comm, options.args)
    parser.exit()


main.commands = {  # type: ignore[attr-defined]
    'helloworld': helloworld,
    'ringtest': ringtest,
    'pingpong': pingpong,
}

if __name__ == '__main__':
    main()
