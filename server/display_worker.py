"""Independent map preparation queue; never claims legacy raster import jobs."""
import logging
import signal
from job_worker import STOP
import import_jobs
import display_jobs


def main():
    from job_worker import main as run_queue
    run_queue()


if __name__=='__main__':main()
