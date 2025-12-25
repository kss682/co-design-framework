import logging
from simpn.reporters import Reporter
from collections import defaultdict

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class TimesReporter(Reporter):

    def __init__(self):
        self.release_time = defaultdict(list)
        self.complete_time = defaultdict(list)
        self.end_to_end = defaultdict(list)

    def callback(self, timed_binding):
        (binding, time, event) = timed_binding
        c_id = binding[0][1].value
        if "generate" in event.get_id():
            self.release_time[c_id].append(time)
        if "to_done" in event.get_id():
            self.complete_time[c_id].append(time)
    
    def validate(self):
        for item in self.complete_time.keys():
            if self.release_time.get(item, None) is not None:
                logger.info(
                        "stream_id release_time complete_time e2e")
                for time in range(len(self.complete_time.get(item))):
                    logger.info(
                        "%s\t%s\t%s\t%s",
                        item,
                        self.release_time[item][time],
                        self.complete_time[item][time],
                        self.complete_time[item][time] - self.release_time[item][time] 
                    )