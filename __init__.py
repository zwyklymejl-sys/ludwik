"""
METHOD REGISTRY

Every method is a module with:
    CODE  - short code, used as key for the output file (see config.OUTPUT_METHOD_FILES)
    NAME  - readable name
    run(data, settings) -> common.MethodResult

To add a method: create a module following method1_paid_to_ultimate.py,
import it here, append it to METHODS and give it an output file name in config.
"""
from . import method1_paid_to_ultimate
from . import method2_paid_to_best_estimate

METHODS = [
    method1_paid_to_ultimate,
    method2_paid_to_best_estimate,
]
