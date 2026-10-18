"""Bounded pre-decided input sequences. Importing this module never sends input."""
from contextlib import contextmanager
import copy
import hashlib
import json
import msvcrt
from pathlib import Path
import threading
import time
import uuid
from .live_control import atomic
from .experience import record


@contextmanager
def input_lock(root):
    path = Path(root)/'.robotomy/live/control/input-sequence.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as stream:
        if path.stat().st_size == 0:
            stream.write(b'0'); stream.flush()
        stream.seek(0)
        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise ValueError('Another input or sequence is active; wait or cancel it.')
        try:
            yield
        finally:
            stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def execute_with_lock(executor, decision_id):
    with input_lock(executor.root):
        return executor.execute(decision_id)


def screen_signature(snapshot):
    # Conservative: any exposed text/button change ends the remaining plan.
    fields = {k:snapshot.get(k) for k in ('process_id','scene','screen','ui_texts','buttons')}
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()


class Sequences:
    def __init__(self, root, executor=None):
        self.root = Path(root)
        if executor is None:
            from .virtual_input import VirtualExecutor
            executor = VirtualExecutor(root)
        self.executor = executor
        self.jobs = {}
        self.guard = threading.Lock()

    def submit(self, decision_ids):
        if not 1 <= len(decision_ids) <= 5 or len(set(decision_ids)) != len(decision_ids):
            raise ValueError('Use 1..5 distinct prepared decision IDs.')
        control = self.executor.control
        decisions = [control._read('decisions/'+control._id(x)+'.json') for x in decision_ids]
        view = control.view()
        if any(d['view_id'] != view['id'] for d in decisions):
            raise ValueError('All decisions must use the same current observed view.')
        if sum(d['duration_ms'] for d in decisions) > 5000:
            raise ValueError('Total input duration must be at most 5000ms.')
        if any((control.directory/'claims'/(d['id']+'.json')).exists() or
               (control.directory/'receipts'/(d['id']+'.json')).exists() for d in decisions):
            raise ValueError('Already attempted decisions cannot be scheduled again.')
        snapshot = self.executor._snapshot()
        if (snapshot['scene'] != view['scene'] or snapshot['process_id'] != view['process_id']
                or snapshot['screen'] != {k:view[k] for k in ('width','height')}):
            raise ValueError('Screen changed; observe again.')
        lease = input_lock(self.root)
        lease.__enter__()  # Synchronously reserve, so accepted means no competing sequence.
        identity = uuid.uuid4().hex
        job = dict(id=identity,status='running',decision_ids=list(decision_ids),receipts=[],
                   cancel_requested=False,stop_reason=None)
        with self.guard:
            self.jobs[identity] = job
        try:
            self.save(job)
            record(self.root,'input_sequence_submitted',copy.deepcopy(job))
            thread = threading.Thread(target=self.run,args=(job,screen_signature(snapshot),lease),daemon=True)
            thread.start()
        except BaseException:
            lease.__exit__(None,None,None)
            raise
        return {'id':identity,'status':'accepted','stop_dispatch_after_seconds':10,
                'cancel_boundary':'After current bounded input; pending steps are cancelled.'}

    def save(self, job):
        atomic(self.root/'.robotomy/live/control/sequences'/(job['id']+'.json'),copy.deepcopy(job))

    def run(self, job, signature, lease):
        deadline = time.monotonic()+10
        last_sequence = None
        try:
            for identity in job['decision_ids']:
                with self.guard:
                    if job['cancel_requested']:
                        job['stop_reason']='cancel_requested'; break
                if time.monotonic() >= deadline:
                    job['stop_reason']='deadline'; break
                snapshot = self.executor._snapshot()
                fresh_deadline = time.monotonic()+1
                while last_sequence is not None and snapshot['sequence'] <= last_sequence:
                    if job['cancel_requested'] or time.monotonic() >= fresh_deadline:
                        break
                    time.sleep(.03)
                    snapshot = self.executor._snapshot()
                if job['cancel_requested']:
                    job['stop_reason']='cancel_requested'; break
                if last_sequence is not None and snapshot['sequence'] <= last_sequence:
                    job['stop_reason']='no_fresh_observation'; break
                if screen_signature(snapshot) != signature:
                    job['stop_reason']='screen_changed'; break
                # Existing executor still checks freshness, pause, save isolation and expiry.
                receipt = self.executor.execute(identity)
                with self.guard:
                    job['receipts'].append(receipt)
                    self.save(job)
                if receipt.get('status') != 'input_sent':
                    job['stop_reason']='input_not_confirmed'; break
                # Preserve receipt even if the following observation becomes unavailable.
                last_sequence = self.executor._snapshot()['sequence']
            with self.guard:
                job['status']='stopped' if job['stop_reason'] else 'completed'
        except Exception as exc:
            with self.guard:
                job.update(status='stopped',stop_reason=str(exc))
        finally:
            try:
                with self.guard:
                    self.save(job)
                    result=copy.deepcopy(job)
            finally:
                lease.__exit__(None,None,None)
            record(self.root,'input_sequence_finished',result)

    def has_active(self):
        with self.guard:
            return any(job['status']=='running' for job in self.jobs.values())

    def status(self, identity):
        with self.guard:
            if identity not in self.jobs:
                raise ValueError('Unknown sequence in this MCP session; never replay automatically.')
            return copy.deepcopy(self.jobs[identity])

    def cancel(self, identity):
        with self.guard:
            if identity not in self.jobs: raise ValueError('Unknown sequence')
            job=self.jobs[identity]
            if job['status']=='running':
                job['cancel_requested']=True
                self.save(job)
            return copy.deepcopy(job)


def register_sequence_tools(server, root, executor=None):
    sequences=Sequences(root, executor)
    server._input_sequences=sequences

    @server.tool()
    def submit_input_sequence(decision_ids: list[str]) -> dict:
        """Submit 1..5 already prepared inputs, <=5s total. Returns immediately.
        Same observed view only; no loops/conditions or automatic new observations.
        Remaining inputs stop on visible text/button, scene, size, process or view change,
        operator stop, expiry, unknown receipt or cancellation. Observe results yourself.
        """
        return sequences.submit(decision_ids)

    @server.tool()
    def input_sequence_status(sequence_id: str) -> dict:
        """Read asynchronous input progress. Completion means delivery, not game success."""
        return sequences.status(sequence_id)

    @server.tool()
    def cancel_input_sequence(sequence_id: str) -> dict:
        """Cancel pending steps; current bounded input may finish (up to 3s plus acknowledgement).
        No global pause and no game pause; cancellation does not undo delivered input.
        """
        return sequences.cancel(sequence_id)
