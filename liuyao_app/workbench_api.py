"""Routes using the same local-session and cross-origin gate as the case APIs."""
from urllib.parse import urlsplit


def dispatch(handler, actor, mutation, body=None, idem=None):
    from .server import ApiError, exact_fields, text_field
    runtime = handler.server.app.workbench
    store = runtime.store
    owner = actor.owner_id
    path = urlsplit(handler.path).path
    parts = path.strip('/').split('/')[2:]
    try:
        if not mutation:
            if parts == ['skills']:
                handler.send_json(runtime.catalog(owner));return
            if parts == ['documents']:
                handler.send_json({'documents': store.documents(owner)});return
            if parts == ['chats']:
                handler.send_json({'chats': store.chats(owner)});return
            if parts == ['issues']:
                handler.send_json({'issues': store.issues(owner)});return
            if parts == ['active']:
                handler.send_json({'jobs': store.pending(owner)});return
            if len(parts) == 3 and parts[0] == 'skills' and parts[2] == 'versions':
                handler.send_json(store.versions(owner, parts[1]));return
            if len(parts) == 2 and parts[0] == 'jobs':
                handler.send_json(store.job(owner, parts[1]));return
            if len(parts) in (2, 3) and parts[0] in ('chats', 'issues'):
                result = store.chat(owner, parts[1]) if parts[0] == 'chats' else store.issue(owner, parts[1])
                if len(parts) == 2:
                    handler.send_json(result);return
                if parts[2] == 'export':
                    handler.send_json({'format': 'skill-' + parts[0] + '-v1', **result},
                                      extra={'Content-Disposition': 'attachment; filename="skill-record.json"'});return
        else:
            if parts == ['documents']:
                handler.send_json(store.add_document(owner, body, idem), 201);return
            if len(parts) == 3 and parts[0] == 'documents' and parts[2] == 'remove':
                exact_fields(body, ())
                handler.send_json(store.remove_document(owner, parts[1], idem));return
            if parts == ['chats']:
                exact_fields(body, ('title',), ('title',))
                handler.send_json(store.create_chat(owner, body['title'], idem), 201);return
            if len(parts) == 3 and parts[0] == 'chats' and parts[2] == 'ask':
                handler.send_json(runtime.enqueue(owner, 'knowledge', parts[1], body, idem), 202);return
            if parts == ['issues']:
                handler.send_json(store.create_issue(owner, body, idem), 201);return
            if len(parts) == 3 and parts[0] == 'issues' and parts[2] == 'process':
                handler.send_json(runtime.enqueue(owner, 'issue', parts[1], body, idem), 202);return
            if len(parts) == 3 and parts[0] == 'skills' and parts[2] == 'rollback':
                exact_fields(body, ('version', 'expected_version'), ('version', 'expected_version'))
                handler.send_json(store.rollback(owner, parts[1], body['version'], body['expected_version'], idem));return
            if parts == ['search']:
                exact_fields(body, ('question',), ('question',))
                handler.send_json({'sources': store.search(owner, text_field(body['question'], 4000))});return
    except ValueError as exc:
        raise ApiError(422, 'WORKBENCH_INVALID', str(exc)) from None
    raise ApiError(404, 'NOT_FOUND', '找不到这个技能记录。')
