"""Independent map preparation queue; never claims legacy raster import jobs."""
import logging
import signal
from job_worker import STOP
import import_jobs
import display_jobs


def main():
    logging.basicConfig(level=logging.INFO)
    signal.signal(signal.SIGTERM,lambda *_:STOP.set());signal.signal(signal.SIGINT,lambda *_:STOP.set())
    while not STOP.is_set():
        try:
            job=import_jobs.claim(table='raster_display_jobs',event_writer=display_jobs.event)
            if job:display_jobs.execute(job)
            else:STOP.wait(2)
        except Exception:
            logging.exception('Map preparation queue unavailable');STOP.wait(5)


if __name__=='__main__':main()
