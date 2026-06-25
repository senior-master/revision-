"""
Curriculum Audit Script
Run this in Termux inside the folder containing your curriculum.json
Usage: python audit_curriculum.py curriculum.json
"""

import json
import sys
from collections import defaultdict


def audit(path: str):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    meta       = data.get("meta", {})
    curriculum = data.get("curriculum", [])

    # ── Counters ──────────────────────────────────────────────────────────────
    total_courses  = len(curriculum)
    total_units    = 0
    total_topics   = 0
    topics_with_coverage = 0
    total_coverage_items = 0

    topic_types    = defaultdict(int)
    priorities     = defaultdict(int)
    groups         = defaultdict(int)
    courses_report = []

    missing_topic_id    = []
    missing_title       = []
    missing_topic_type  = []
    duplicate_topic_ids = []
    seen_topic_ids      = set()

    for course in curriculum:
        course_id   = course.get("course_id", "UNKNOWN")
        course_name = course.get("course_name", "UNKNOWN")
        priority    = course.get("priority", "none")
        group       = course.get("group", "none")
        units       = course.get("units", [])

        priorities[priority] += 1
        groups[group]        += 1

        course_topics = 0
        course_units  = len(units)
        total_units  += course_units

        for unit in units:
            topics = unit.get("topics", [])
            for topic in topics:
                total_topics  += 1
                course_topics += 1

                tid   = topic.get("topic_id")
                title = topic.get("title")
                ttype = topic.get("topic_type")
                cov   = topic.get("coverage", [])

                if not tid:
                    missing_topic_id.append(f"{course_id} > {title}")
                elif tid in seen_topic_ids:
                    duplicate_topic_ids.append(tid)
                else:
                    seen_topic_ids.add(tid)

                if not title:
                    missing_title.append(tid or "NO_ID")
                if not ttype:
                    missing_topic_type.append(tid or title or "UNKNOWN")
                else:
                    topic_types[ttype] += 1

                if cov:
                    topics_with_coverage   += 1
                    total_coverage_items   += len(cov)

        courses_report.append({
            "id":     course_id,
            "name":   course_name,
            "group":  group,
            "priority": priority,
            "units":  course_units,
            "topics": course_topics
        })

    # ── Print Report ──────────────────────────────────────────────────────────
    sep = "=" * 55

    print(f"\n{sep}")
    print("  CURRICULUM AUDIT REPORT")
    print(sep)

    print(f"\n── META ──────────────────────────────────────────────")
    print(f"  Declared total topics : {meta.get('total_topics', 'N/A')}")
    print(f"  Target date           : {meta.get('target_date', 'N/A')}")

    print(f"\n── STRUCTURE ─────────────────────────────────────────")
    print(f"  Total courses         : {total_courses}")
    print(f"  Total units           : {total_units}")
    print(f"  Total topics (actual) : {total_topics}")
    print(f"  Topics with coverage  : {topics_with_coverage}")
    print(f"  Total coverage items  : {total_coverage_items}")
    avg_cov = total_coverage_items / topics_with_coverage if topics_with_coverage else 0
    print(f"  Avg coverage per topic: {avg_cov:.1f}")

    declared = meta.get("total_topics", 0)
    if declared and declared != total_topics:
        print(f"\n  ⚠️  MISMATCH: declared {declared} but found {total_topics}")
    else:
        print(f"\n  ✅ Topic count matches meta declaration")

    print(f"\n── COURSES BREAKDOWN ─────────────────────────────────")
    print(f"  {'ID':<15} {'Group':<15} {'Pri':<8} {'Units':<7} {'Topics'}")
    print(f"  {'-'*55}")
    for c in sorted(courses_report, key=lambda x: x["topics"], reverse=True):
        print(f"  {c['id']:<15} {c['group']:<15} {c['priority']:<8} {c['units']:<7} {c['topics']}")

    print(f"\n── TOPIC TYPES ───────────────────────────────────────")
    for k, v in sorted(topic_types.items(), key=lambda x: x[1], reverse=True):
        bar = "█" * (v // 5)
        print(f"  {k:<30} {v:>4}  {bar}")

    print(f"\n── PRIORITY DISTRIBUTION ─────────────────────────────")
    for k, v in sorted(priorities.items(), key=lambda x: x[1], reverse=True):
        print(f"  {k:<20} {v} courses")

    print(f"\n── GROUP DISTRIBUTION ────────────────────────────────")
    for k, v in sorted(groups.items(), key=lambda x: x[1], reverse=True):
        print(f"  {k:<20} {v} courses")

    print(f"\n── DATA QUALITY ──────────────────────────────────────")
    print(f"  Missing topic_id      : {len(missing_topic_id)}")
    print(f"  Missing title         : {len(missing_title)}")
    print(f"  Missing topic_type    : {len(missing_topic_type)}")
    print(f"  Duplicate topic_ids   : {len(duplicate_topic_ids)}")

    if missing_topic_id:
        print(f"\n  Topics missing ID:")
        for t in missing_topic_id[:10]:
            print(f"    - {t}")

    if duplicate_topic_ids:
        print(f"\n  Duplicate IDs found:")
        for t in duplicate_topic_ids[:10]:
            print(f"    - {t}")

    if missing_topic_type:
        print(f"\n  Topics missing type (first 10):")
        for t in missing_topic_type[:10]:
            print(f"    - {t}")

    print(f"\n── CONTENT POTENTIAL ─────────────────────────────────")
    posts_per_topic = 6  # 6 content types per topic
    total_potential = total_topics * posts_per_topic
    at_8_per_day    = total_potential / 8
    print(f"  Topics                : {total_topics}")
    print(f"  Content types planned : {posts_per_topic}")
    print(f"  Total content potential: {total_potential} posts")
    print(f"  At 8 posts/day        : {at_8_per_day:.0f} days ({at_8_per_day/365:.1f} years)")

    print(f"\n{sep}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python audit_curriculum.py curriculum.json")
        sys.exit(1)
    audit(sys.argv[1])

