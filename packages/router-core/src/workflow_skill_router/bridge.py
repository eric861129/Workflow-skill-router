from __future__ import annotations

from hashlib import sha256
import json
import sys
import traceback
from typing import TextIO

from workflow_skill_router.service_codecs import ServiceCodecError
from workflow_skill_router.runtime_readiness import CapabilityUnavailable
from workflow_skill_router.tool_dispatch import PUBLIC_TOOLS


MAX_LINE_BYTES = 4 * 1024 * 1024


def serve(source: TextIO, output: TextIO, dispatcher, diagnostics: TextIO | None = None) -> None:
    diagnostics = diagnostics or sys.stderr
    seen: set[str] = set()
    for line in source:
        request_id = "invalid"
        try:
            if len(line.encode("utf-8")) > MAX_LINE_BYTES: raise ServiceCodecError("line-too-large")
            request = json.loads(line)
            if not isinstance(request, dict) or set(request) != {"request_id", "tool", "arguments"}:
                raise ServiceCodecError("request-shape-invalid")
            request_id, tool, arguments = request["request_id"], request["tool"], request["arguments"]
            if not isinstance(request_id, str) or not request_id or request_id in seen:
                raise ServiceCodecError("request-id-invalid")
            seen.add(request_id)
            if not isinstance(tool, str) or tool not in PUBLIC_TOOLS: raise LookupError(str(tool))
            if not isinstance(arguments, dict): raise ServiceCodecError("arguments-invalid")
            response = {"request_id": request_id, "ok": True, "result": dispatcher.dispatch(tool, arguments)}
        except LookupError:
            response = {"request_id": request_id, "ok": False,
                        "error": {"code": "unknown-tool", "message": "Unknown public tool"}}
        except ServiceCodecError:
            response = {"request_id": request_id, "ok": False,
                        "error": {"code": "invalid-arguments", "message": "Invalid request arguments"}}
        except CapabilityUnavailable as error:
            response = {
                "request_id": request_id,
                "ok": False,
                "error": error.public_payload(),
            }
        except Exception as error:
            correlation = sha256(f"{type(error).__name__}:{request_id}".encode()).hexdigest()[:16]
            print(f"[{correlation}] {type(error).__name__}: {error}", file=diagnostics)
            traceback.print_exception(error, file=diagnostics)
            response = {"request_id": request_id, "ok": False,
                        "error": {"code": "internal-error", "message": f"correlation:{correlation}"}}
        output.write(json.dumps(response, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
        output.flush()
