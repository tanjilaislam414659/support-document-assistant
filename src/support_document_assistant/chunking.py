"""Conservative, deterministic RST blocks. Source text is never evaluated."""
import re

from .assets import json_bytes, sha256


def indentation(line):
    return len(line) - len(line.lstrip(" "))


def adornment(line):
    text = line.strip()
    return text[0] if len(text) >= 3 and len(set(text)) == 1 and text[0] in "=*-~^#+" else None


def heading_at(lines, i):
    if not lines[i].strip() or lines[i][0].isspace():
        return None
    if i + 2 < len(lines) and adornment(lines[i]) and lines[i].strip() == lines[i + 2].strip():
        if lines[i + 1].strip() and not lines[i + 1][0].isspace():
            return i + 3, lines[i + 1].strip(), (adornment(lines[i]), "overline")
    if i + 1 < len(lines) and not adornment(lines[i]) and adornment(lines[i + 1]):
        return i + 2, lines[i].strip(), (adornment(lines[i + 1]), "underline")
    return None


DIRECTIVE = re.compile(r"^\s*\.\. ([a-zA-Z][\w-]*)::(?:\s*(.*))?$")
BULLET = re.compile(r"^(\s*)(?:[*+-]|\d+[.)])\s+")


def source_blocks(text, source_id, policy, issues):
    """Yield source blocks and explicit barriers/omissions, with exact raw slices."""
    lines = text.splitlines(keepends=True)
    offsets, total = [], 0
    for line in lines:
        offsets.append(total)
        total += len(line)
    banned = {}
    for issue in issues:
        if issue["source_id"] != source_id:
            continue
        a, b = issue["lines"]
        if not 1 <= a <= b <= len(lines):
            raise ValueError("Exclusion lines outside source")
        for n in range(a - 1, b):
            if n in banned:
                raise ValueError("Overlapping source exclusions")
            banned[n] = issue
    styles, stack = [], []

    def finish(a, b, kind, section):
        while b > a and not lines[b - 1].strip():
            b -= 1
        raw_text = "".join(lines[a:b]).rstrip("\r\n")
        return {"kind": kind, "source_lines": [a + 1, b],
                "source_char_range": [offsets[a], offsets[a] + len(raw_text)],
                "section_titles": list(section), "text": raw_text}

    def indented_end(a, base):
        j = a + 1
        last = j
        while j < len(lines) and j not in banned:
            if not lines[j].strip():
                j += 1
                continue
            if indentation(lines[j]) <= base:
                break
            last = j + 1
            j += 1
        return last

    i = 0
    while i < len(lines):
        if i in banned:
            issue = banned[i]
            end = issue["lines"][1]
            yield {"kind": "excluded", "source_lines": issue["lines"],
                   "reason": "source_quality", "details": issue}
            i = end
            continue
        if not lines[i].strip():
            i += 1
            continue
        heading = heading_at(lines, i)
        if heading:
            end, title, style = heading
            if style not in styles:
                styles.append(style)
            level = styles.index(style)
            stack = stack[:level] + [title]
            yield finish(i, end, "heading", stack)
            i = end
            continue
        directive = DIRECTIVE.match(lines[i])
        if directive:
            name, target = directive.groups()
            end = indented_end(i, indentation(lines[i]))
            if name in policy["unsupported_directives"]:
                yield {"kind": "excluded", "source_lines": [i + 1, end],
                       "reason": "unresolved_include" if name in ("include", "literalinclude") else "unsupported_directive",
                       "details": {"directive": name, "target": target or "", "fetched": False}}
            else:
                yield finish(i, end, name, stack)
            i = end
            continue
        if lines[i].lstrip().startswith("+") and re.match(r"^[+\-=\s]+$", lines[i]):
            end = i + 1
            while end < len(lines) and end not in banned and lines[end].lstrip().startswith(("|", "+")):
                end += 1
            yield finish(i, end, "grid_table", stack)
            i = end
            continue
        if indentation(lines[i]) > 0:
            end = indented_end(i, indentation(lines[i]) - 1)
            yield finish(i, end, "indented", stack)
            i = end
            continue
        end = i + 1
        while end < len(lines) and end not in banned and lines[end].strip():
            if heading_at(lines, end) or DIRECTIVE.match(lines[end]) or BULLET.match(lines[end]):
                break
            end += 1
        kind = "list_item" if BULLET.match(lines[i]) else "paragraph"
        if lines[end - 1].rstrip().endswith("::"):
            literal_end = indented_end(end - 1, indentation(lines[i]))
            if literal_end > end:
                end, kind = literal_end, "literal_block"
        yield finish(i, end, kind, stack)
        i = end


def chunk_source(raw, source, policy, issues, policy_sha256):
    text = raw.decode("utf-8", errors="strict")
    raw_hash = sha256(raw)
    chunks, exclusions, pending = [], [], []
    covered = set()

    def flush():
        if not pending:
            return
        parts, segments, length = [], [], 0
        for block in pending:
            if parts:
                length += 2
            start = length
            parts.append(block["text"])
            length += len(block["text"])
            segments.append({key: block[key] for key in ("source_lines", "source_char_range", "kind")})
            segments[-1]["chunk_char_range"] = [start, length]
            covered.update(range(block["source_lines"][0], block["source_lines"][1] + 1))
        chunk_text = "\n\n".join(parts)
        identity = {"source_id": source["source_id"], "source_sha256": raw_hash,
                    "policy_sha256": policy_sha256, "parser_version": policy["parser_version"],
                    "section_titles": pending[0]["section_titles"], "segments": segments,
                    "text_sha256": sha256(chunk_text.encode("utf-8"))}
        chunks.append({**identity, "chunk_id": "chunk-" + sha256(json_bytes(identity)),
                       "product_version": source["product_version"],
                       "immutable_url": source["immutable_url"], "source_path": source["path"],
                       "source_git_blob_sha1": source["git_blob_sha1"],
                       "line_start": segments[0]["source_lines"][0],
                       "line_end": segments[-1]["source_lines"][1],
                       "character_count": len(chunk_text),
                       "over_target_atomic": len(chunk_text) > policy["target_characters"],
                       "text": chunk_text, "eligible_for_answer_support": True})
        pending.clear()

    for block in source_blocks(text, source["source_id"], policy, issues):
        if block["kind"] == "excluded":
            flush()
            exclusions.append({"source_id": source["source_id"], **block})
            covered.update(range(block["source_lines"][0], block["source_lines"][1] + 1))
            continue
        if len(block["text"]) > policy["max_atomic_characters"]:
            flush()
            exclusion = {"source_id": source["source_id"], "kind": "excluded",
                         "reason": "oversized_atomic_block", "source_lines": block["source_lines"],
                         "details": {"characters": len(block["text"]), "block_kind": block["kind"]}}
            exclusions.append(exclusion)
            covered.update(range(block["source_lines"][0], block["source_lines"][1] + 1))
            continue
        packed_length = sum(len(b["text"]) for b in pending) + len(block["text"]) + 2 * len(pending)
        if pending and (pending[0]["section_titles"] != block["section_titles"] or
                        packed_length > policy["target_characters"]):
            flush()
        pending.append(block)
        if len(block["text"]) > policy["target_characters"]:
            flush()
    flush()
    missing = [i + 1 for i, line in enumerate(text.splitlines()) if line.strip() and i + 1 not in covered]
    if missing:
        raise ValueError(f"Unreported nonblank content loss: {source['source_id']} {missing}")
    return chunks, exclusions
