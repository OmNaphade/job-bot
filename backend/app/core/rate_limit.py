from slowapi import Limiter
from slowapi.util import get_remote_address

# One shared instance: main.py wires it into the app (state + exception
# handler + middleware), routes.py's signup/login handlers apply it via
# @limiter.limit(...). In-memory storage (the default) is fine at this
# project's scale -- a single API process, no Redis needed. Per-IP via
# get_remote_address -- open signup (no invite code by default) means this is
# what actually stands between a public deployment and someone scripting
# account creation or password-guessing.
limiter = Limiter(key_func=get_remote_address)
