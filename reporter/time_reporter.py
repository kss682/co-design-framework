import logging
from models.stream import Packet
from simpn.reporters import Reporter
from collections import defaultdict

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class TimesReporter(Reporter):

    def __init__(self, generate_events, done_events, streams):
        self.end_to_end = defaultdict(dict)
        self.generate_events = generate_events
        self.done_events = done_events
        self.streams = streams
        logger.info(f"registering generate_events: {generate_events}")
        logger.info(f"registering generate_events: {done_events}")

    def callback(self, timed_binding):
        (binding, time, event) = timed_binding

        for bind in binding:
            token = bind[1].value

            if event.get_id() in self.generate_events and isinstance(token, Packet):
                if token.stream_id not in self.end_to_end:
                     self.end_to_end[token.stream_id] = {}
                self.end_to_end[token.stream_id][token.seq_id] = { "release_time": time }
            # logger.info(self.end_to_end)
            if event.get_id() in self.done_events and isinstance(token, Packet):
                if token.stream_id in self.end_to_end and token.seq_id in self.end_to_end[token.stream_id]:
                    self.end_to_end[token.stream_id][token.seq_id]["complete_time"] = time
                else:
                    logger.warning(f"Done event for {token.stream_id}/{token.seq_id} but no generate event found")


    def e2e_validate(self):
        headers = ["Stream", "Seq", "Release", "Complete", "Latency", "Deadline", "Check"]
        rows = []
        for stream_id, packets in self.end_to_end.items():
            for pack_id, times in packets.items():
                # print(times)
                release = times.get("release_time")
                complete = times.get("complete_time", None)
                # print(complete, release)
                deadline = self.streams.get(stream_id).deadline
                end_to_end = None
                if release is not None and complete is not None:
                    end_to_end = complete - release            
                rows.append([
                    stream_id,
                    pack_id,
                    release,
                    complete,
                    end_to_end,                    
                    deadline,
                    "Satisfied"
                    if end_to_end is not None and end_to_end <= deadline
                    else "Violated"
                ])

        col_widths = [
            max(len(str(row[i])) for row in [headers] + rows)
            for i in range(len(headers))
        ]

        def fmt(row):
            return " | ".join(
                str(row[i]).ljust(col_widths[i])
                for i in range(len(row))
            )

        sep = "-+-".join("-" * w for w in col_widths)

        table = [
            fmt(headers),
            sep,
            *(fmt(r) for r in rows)
        ]
        print("\n".join(table))