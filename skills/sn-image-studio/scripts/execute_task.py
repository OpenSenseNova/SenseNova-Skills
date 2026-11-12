#!/usr/bin/env python3
"""Publish a job action atomically; wait for Studio's durable receipt (no network)."""
import argparse
import json
import os
from pathlib import Path
import time
import uuid
from execution_limits import TASK_RECEIPT_TIMEOUT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result', type=Path, required=True)
    args = parser.parse_args()
    directory = Path(__file__).resolve().parent
    try:
        job = json.loads((directory / 'job-access.json').read_text(encoding='utf-8'))
        result = args.result.resolve()
        if result != directory / 'rewrite-result.json' or result.stat().st_size > 262144:
            raise ValueError('Invalid result file')
        body = {'request_id': job['request_id'], 'token': job['token'],
                'response': json.loads(result.read_text(encoding='utf-8'))}
        destination = directory / 'execution-request.json'
        temporary = directory / f'execution-{uuid.uuid4().hex}.tmp'
        temporary.write_text(json.dumps(body, ensure_ascii=False), encoding='utf-8')
        try:
            # Atomic, exclusive publication: the backend never reads a partial file.
            os.link(temporary, destination)
        except FileExistsError:
            if json.loads(destination.read_text(encoding='utf-8')) != body:
                raise ValueError('A different result has already been submitted')
        finally:
            temporary.unlink(missing_ok=True)
        deadline = time.monotonic() + TASK_RECEIPT_TIMEOUT
        receipt = directory / 'execution-receipt.json'
        while time.monotonic() < deadline:
            if receipt.is_file():
                task = json.loads(receipt.read_text(encoding='utf-8'))
                print(json.dumps(task, ensure_ascii=False))
                return 0 if task['status'] == 'succeeded' else 1
            time.sleep(.1)
        raise TimeoutError('Unconfirmed task result')
    except TimeoutError:
        print(json.dumps({'status': 'failed', 'error': f'等待后端任务回执超时（{TASK_RECEIPT_TIMEOUT} 秒）；结果尚未确认，请检查原任务，不要自动重试生图。'}, ensure_ascii=False))
        return 1
    except (OSError, ValueError, KeyError):
        print(json.dumps({'status': 'failed', 'error': '任务脚本未完成；请检查原任务状态，不要自动重试生图。'}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
