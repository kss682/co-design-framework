from loguru import logger
from models.stream import Packet
from simpn.reporters import Reporter
from collections import defaultdict
from reporter.delivery_constraints import PacketDeliveryConstraints


class TimesReporter(Reporter):

    def __init__(self, generate_events, done_events, streams, delivery_constraints):
        self.end_to_end = defaultdict(dict)
        self.generate_events = generate_events
        self.done_events = done_events
        self.streams = streams
        self.delivery_constraints = delivery_constraints
        self.delivery_status = defaultdict(list)
        logger.info(f"registering generate_events: {generate_events}")
        logger.info(f"registering generate_events: {done_events}")

    def callback(self, timed_binding):
        (binding, time, event) = timed_binding

        for bind in binding:
            token = bind[1].value

            if event.get_id() in self.generate_events and isinstance(token, Packet):
                if (token.mode_seq, token.stream_id) not in self.end_to_end:
                     self.end_to_end[(token.mode_seq, token.stream_id)] = {}
                self.end_to_end[(token.mode_seq, token.stream_id)][token.seq_id] = { "release_time": time }
            # logger.info(self.end_to_end)
            if event.get_id() in self.done_events and isinstance(token, Packet):
                if (token.mode_seq, token.stream_id) in self.end_to_end and token.seq_id in self.end_to_end[(token.mode_seq, token.stream_id)]:
                    self.end_to_end[(token.mode_seq, token.stream_id)][token.seq_id]["complete_time"] = time
                else:
                    logger.warning(f"Done event for {token.stream_id}/{token.seq_id} but no generate event found")


    def e2e_validate(self):
        headers = ["Mode", "Stream", "Seq", "Release", "Complete", "Latency", "Deadline", "Check"]
        rows = []
        for key, packets in self.end_to_end.items():
            mode_seq, stream_id = key
            for pack_id, times in packets.items():
                
                release = times.get("release_time")
                complete = times.get("complete_time", None)
                
                deadline = self.streams.get(stream_id).deadline
                end_to_end = None
                if release is not None and complete is not None:
                    end_to_end = complete - release

                status = "Violated"
                if end_to_end is not None and end_to_end <= deadline:
                    status = "Satisfied"
                
                self.delivery_status[(mode_seq, stream_id)].append(status)

                rows.append([
                    mode_seq.split("@")[0],
                    stream_id,
                    pack_id,
                    release,
                    complete,
                    end_to_end,                    
                    deadline,
                    status
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
        table = "\n".join(table)
        logger.info("\n{}", table)


    def validate_throuput(self):
        logger.info(self.delivery_constraints)
        results = dict()
        for key, packet in self.end_to_end.items():
            mode_seq, stream_id = key
            mode_id = int(mode_seq.split('@')[0])
            min_packets = self.delivery_constraints.get((mode_id, stream_id)).min_packets
            window_size = self.delivery_constraints.get((mode_id, stream_id)).window_size

            violated_count = 0
            status = self.delivery_status.get((mode_seq, stream_id))

            for i in range(min(window_size, len(status))):
                if status[i] == "Violated":
                    violated_count += 1
            
            if violated_count > window_size - min_packets:
                results[(mode_seq, stream_id)] = "Violated"
                continue

            for i in range(window_size, len(status)):
                if status[i] == "Violated":
                    violated_count += 1
                if status[i-window_size] == "Violated":
                    violated_count -= 1
                if violated_count > window_size - min_packets:
                    results[(mode_seq, stream_id)] = "Violated"
                    break
            
            if results.get((mode_seq, stream_id), None) is not None:
                continue

            results[(mode_seq, stream_id)] = "Satisfied"

        for key, status in results.items():
            mode_seq, stream_id = key
            mode_id = int(mode_seq.split('@')[0])

            min_packets = self.delivery_constraints.get((mode_id, stream_id)).min_packets
            window_size = self.delivery_constraints.get((mode_id, stream_id)).window_size

            logger.info(f"Delivery constraint of {min_packets}/{window_size} (min_packet/window) for mode {mode_seq} with stream {stream_id} is {status}")
