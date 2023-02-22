# pylint: disable=import-error,no-name-in-module
import json
import os
from multiprocessing import freeze_support

import pyperf

from benchmarks.pybench.utils import load_by_object_ref


def main():
    bench_name = os.environ['PYBENCH_NAME']
    func = load_by_object_ref(os.environ['PYBENCH_ENTRYPOINT'])
    params = json.loads(os.environ['PYBENCH_PARAMS'])

    benchmark_plan = func(*params)
    runner = pyperf.Runner()
    runner.bench_func(
        bench_name,
        benchmark_plan.func,
        *benchmark_plan.args,
    )


if __name__ == '__main__':
    freeze_support()
    main()
