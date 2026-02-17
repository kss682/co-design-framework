import os
import csv
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
        self.csv_data = []

    def callback(self, timed_binding):
        (binding, time, event) = timed_binding

        for bind in binding:
            token = bind[1].value
            
            if (event.get_id() in self.generate_events and isinstance(token, Packet) and str(token.stream_id) in event.get_id()):
                stream_id = token.stream_id
                if (token.mode_seq, stream_id) not in self.end_to_end:
                     self.end_to_end[(token.mode_seq, stream_id)] = {}
                self.end_to_end[(token.mode_seq, stream_id)][token.seq_id] = { "release_time": time}


            if event.get_id() in self.done_events and isinstance(token, Packet):
                # For generate_events that are also done_events (triggered streams),
                # only record completion for the triggering packet, not the newly generated one
                if event.get_id() in self.generate_events and str(token.stream_id) in event.get_id():
                    # This is the newly generated packet - skip completion recording
                    continue

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
        # logger.info("\n{}", table)


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


    def write(self, output_dir="simulation_results"):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        for st_id, st in self.streams.items():
            src_filename = os.path.join(output_dir, f"{st.src.node_id}_sourc.csv")
            dst_filename = os.path.join(output_dir, f"{st.dst.node_id}_dest.csv")

            with open(src_filename, mode='a', newline='') as src_file:
                writer = csv.writer(src_file)
                # writer.writerow(["mode", "release_time"])

                # Filter end_to_end for packets belonging to this stream
                for key, packet_info in self.end_to_end.items():
                    mode_seq, stream_id = key
                    mode_id = int(mode_seq.split('@')[0])
                    for pack_id, times in packet_info.items():
                
                        release = times.get("release_time")
                        complete = times.get("complete_time", None)
                        if stream_id == st_id and complete is not None:
                            writer.writerow([mode_id, release, pack_id])

            with open(dst_filename, mode='a', newline='') as dst_file:
                writer = csv.writer(dst_file)
                # writer.writerow(["mode", "completion_time"])

                for key, packet_info in self.end_to_end.items():
                    mode_seq, stream_id = key
                    mode_id = int(mode_seq.split('@')[0])
                    for pack_id, times in packet_info.items():
                
                        release = times.get("release_time")
                        complete = times.get("complete_time", None)
                        if stream_id == st_id and complete is not None:
                            writer.writerow([mode_id, complete, pack_id])
        print(f"Data split successful. Files generated in '{output_dir}'")

    def write_plant_traces(self, plant_streams, output_dir="simulation_results"):
        """
        Generate merged trace files per plant for dual-pendulum simulation.

        :param plant_streams: dict mapping plant_id to dict with 'sensor' and 'control' stream lists
                              e.g., {1: {'sensor': [1, 5], 'control': [2, 6]},
                                     2: {'sensor': [3, 7], 'control': [4, 8]}}
        :param output_dir: directory to write output files
        """
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        for plant_id, stream_info in plant_streams.items():
            sensor_streams = set(stream_info.get('sensor', []))
            control_streams = set(stream_info.get('control', []))

            # Collect all events for this plant
            events = []

            for key, packet_info in self.end_to_end.items():
                mode_seq, stream_id = key
                mode_id = int(mode_seq.split('@')[0])

                for pack_id, times in packet_info.items():
                    release = times.get("release_time")
                    complete = times.get("complete_time", None)

                    if stream_id in sensor_streams:
                        # Sensor stream: plantsend at release, controllerreceive at complete
                        if release is not None:
                            events.append((release, "plantsend", mode_id, pack_id))
                        if complete is not None:
                            events.append((complete, "controllerreceive", mode_id, pack_id))

                    elif stream_id in control_streams:
                        # Control stream: plantreceive at complete
                        if complete is not None:
                            events.append((complete, "plantreceive", mode_id, pack_id))

            # Sort events by time
            events.sort(key=lambda x: x[0])

            # Write to file
            filename = os.path.join(output_dir, f"plant{plant_id}_trace.csv")
            with open(filename, mode='w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["# t", "event_type", "mode", "packet_id"])
                for event in events:
                    writer.writerow(event)

            logger.info(f"Plant {plant_id} trace written to {filename} ({len(events)} events)")