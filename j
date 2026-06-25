"""
Curriculum Audit Script v2 — with full course names
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

    total_units    = 0
    total_topics   = 0
    topics_with_coverage   = 0
    total_coverage_items   = 0

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
                    topics_with_coverage += 1
                    total_coverage_items += len(cov)

        courses_report.append({
            "id":       course_id,
            "name":     course_name,
            "group":    group,
            "priority": priority,
            "units":    course_units,
            "topics":   course_topics
        })

    sep = "=" * 70

    print(f"\n{sep}")
    print("  CURRICULUM AUDIT REPORT")
    print(sep)

    print(f"\n── META ──────────────────────────────────────────────────────────────")
    print(f"  Declared total topics : {meta.get('total_topics', 'N/A')}")
    print(f"  Target date           : {meta.get('target_date', 'N/A')}")

    print(f"\n── STRUCTURE ─────────────────────────────────────────────────────────")
    print(f"  Total courses         : {len(curriculum)}")
    print(f"  Total units           : {total_units}")
    print(f"  Total topics (actual) : {total_topics}")
    print(f"  Topics with coverage  : {topics_with_coverage}")
    print(f"  Topics without coverage: {total_topics - topics_with_coverage}")
    print(f"  Total coverage items  : {total_coverage_items}")

    declared = meta.get("total_topics", 0)
    if declared and declared != total_topics:
        print(f"\n  ⚠️  MISMATCH: declared {declared} but found {total_topics}")
    else:
        print(f"  ✅ Topic count matches meta declaration")

    print(f"\n── COURSES BREAKDOWN (sorted by topic count) ─────────────────────────")
    print(f"  {'ID':<12} {'Topics':<8} {'Units':<7} {'Group':<14} {'Course Name'}")
    print(f"  {'-'*68}")
    for c in sorted(courses_report, key=lambda x: x["topics"], reverse=True):
        print(f"  {c['id']:<12} {c['topics']:<8} {c['units']:<7} {c['group']:<14} {c['name']}")

    print(f"\n── TOPIC TYPES (top 15) ──────────────────────────────────────────────")
    sorted_types = sorted(topic_types.items(), key=lambda x: x[1], reverse=True)
    for k, v in sorted_types[:15]:
        bar = "█" * (v // 10)
        pct = (v / total_topics) * 100
        print(f"  {k:<32} {v:>4}  ({pct:4.1f}%)  {bar}")
    if len(sorted_types) > 15:
        others = sum(v for _, v in sorted_types[15:])
        print(f"  {'(other types combined)':<32} {others:>4}")

    print(f"\n── GROUP DISTRIBUTION ────────────────────────────────────────────────")
    for k, v in sorted(groups.items(), key=lambda x: x[1], reverse=True):
        print(f"  {k:<25} {v} courses")

    print(f"\n── DATA QUALITY ──────────────────────────────────────────────────────")
    print(f"  Missing topic_id      : {len(missing_topic_id)}")
    print(f"  Missing title         : {len(missing_title)}")
    print(f"  Missing topic_type    : {len(missing_topic_type)}")
    print(f"  Duplicate topic_ids   : {len(duplicate_topic_ids)}")
    if len(missing_topic_id) + len(missing_title) + len(missing_topic_type) + len(duplicate_topic_ids) == 0:
        print(f"  ✅ No data quality issues found")

    print(f"\n── CONTENT POTENTIAL ─────────────────────────────────────────────────")
    for types_count in [3, 6, 8]:
        potential = total_topics * types_count
        days      = potential / 8
        print(f"  {types_count} content types/topic → {potential:,} posts → {days:.0f} days ({days/365:.1f} yrs)")

    print(f"\n{sep}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python audit_curriculum.py curriculum.json")
        sys.exit(1)
    audit(sys.argv[1])
