#!/usr/bin/env python3
"""
Normalize Livox LVX rosbag timestamps for FAST-LIO2.

Some LVX conversions produce a bag where one topic is recorded near Unix epoch
0 while the LiDAR topic is recorded with GNSS/UTC time. rosbag play then fails
with "Duration is out of dual 32-bit range". This script rewrites the bag using
message header stamps when they are valid and remaps invalid IMU stamps into the
LiDAR time window by preserving their relative order.
"""

import argparse
import datetime as dt
import re
import sys

import rosbag
import rospy


MIN_VALID_UNIX = 1_000_000_000.0


def stamp_to_sec(stamp):
    return float(stamp.secs) + float(stamp.nsecs) * 1e-9


def get_header_time(msg):
    header = getattr(msg, "header", None)
    stamp = getattr(header, "stamp", None)
    if stamp is None:
        return None
    return stamp_to_sec(stamp)


def collect_stats(input_bag):
    stats = {}
    counts = {}

    with rosbag.Bag(input_bag, "r") as bag:
        for topic, msg, t in bag.read_messages():
            header_time = get_header_time(msg)
            record_time = stamp_to_sec(t)
            counts[topic] = counts.get(topic, 0) + 1
            topic_stats = stats.setdefault(
                topic,
                {
                    "count": 0,
                    "record_min": None,
                    "record_max": None,
                    "header_min": None,
                    "header_max": None,
                    "invalid_header": 0,
                },
            )
            topic_stats["count"] += 1
            topic_stats["record_min"] = record_time if topic_stats["record_min"] is None else min(topic_stats["record_min"], record_time)
            topic_stats["record_max"] = record_time if topic_stats["record_max"] is None else max(topic_stats["record_max"], record_time)

            if header_time is None or header_time < MIN_VALID_UNIX:
                topic_stats["invalid_header"] += 1
            else:
                topic_stats["header_min"] = header_time if topic_stats["header_min"] is None else min(topic_stats["header_min"], header_time)
                topic_stats["header_max"] = header_time if topic_stats["header_max"] is None else max(topic_stats["header_max"], header_time)
    return stats, counts


def start_time_from_name(path):
    match = re.search(r"(\d{4}-\d{2}-\d{2})T(\d{2})-(\d{2})-(\d{2})Z", path)
    if not match:
        match = re.search(r"(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})-(\d{2})", path)
    if not match:
        return MIN_VALID_UNIX

    date_part, hour, minute, second = match.groups()
    stamp = dt.datetime.fromisoformat(f"{date_part}T{hour}:{minute}:{second}+00:00")
    return stamp.timestamp()


def set_message_time(msg, out_time):
    if hasattr(msg, "header"):
        msg.header.stamp = rospy.Time.from_sec(out_time)
    if hasattr(msg, "timebase"):
        msg.timebase = int(out_time * 1_000_000_000)


def normalize_bag(input_bag, output_bag):
    stats, counts = collect_stats(input_bag)

    lidar_count = sum(count for topic, count in counts.items() if "lidar" in topic)
    imu_count = sum(count for topic, count in counts.items() if "imu" in topic)
    if lidar_count == 0:
        raise RuntimeError("Nao encontrei mensagens LiDAR")
    if imu_count == 0:
        raise RuntimeError("Nao encontrei mensagens IMU")

    start_time = start_time_from_name(input_bag)
    duration = max((lidar_count - 1) / 10.0, (imu_count - 1) / 200.0, 1.0)
    topic_seen = {}

    written = 0
    dropped = 0

    with rosbag.Bag(input_bag, "r") as src, rosbag.Bag(output_bag, "w") as dst:
        for topic, msg, t in src.read_messages():
            index = topic_seen.get(topic, 0)
            topic_seen[topic] = index + 1

            if "lidar" in topic:
                topic_count = max(counts.get(topic, 1) - 1, 1)
                out_time = start_time + duration * index / topic_count
            elif "imu" in topic:
                topic_count = max(counts.get(topic, 1) - 1, 1)
                out_time = start_time + duration * index / topic_count
            else:
                dropped += 1
                continue

            set_message_time(msg, out_time)
            dst.write(topic, msg, rospy.Time.from_sec(out_time))
            written += 1

    print(f"Bag normalizado: {output_bag}")
    print(f"Janela sintetica: {start_time:.6f} -> {start_time + duration:.6f} ({duration:.3f}s)")
    print(f"LiDAR mensagens: {lidar_count}")
    print(f"IMU mensagens: {imu_count}")
    print(f"Mensagens escritas: {written}")
    print(f"Mensagens descartadas: {dropped}")
    for topic, topic_stats in sorted(stats.items()):
        print(
            f"{topic}: count={topic_stats['count']} "
            f"record=[{topic_stats['record_min']}, {topic_stats['record_max']}] "
            f"header=[{topic_stats['header_min']}, {topic_stats['header_max']}] "
            f"invalid_header={topic_stats['invalid_header']}"
        )


def main():
    parser = argparse.ArgumentParser(description="Normalizar timestamps de rosbag Livox")
    parser.add_argument("input_bag")
    parser.add_argument("output_bag")
    args = parser.parse_args()
    try:
        normalize_bag(args.input_bag, args.output_bag)
    except Exception as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
