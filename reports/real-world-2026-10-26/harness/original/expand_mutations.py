"""Repeat the validated core cases on every remaining comparable Maven consumer."""
import concurrent.futures
import argparse
import json
from campaign import HERE, write_results
from mutate_maven import mutate

def one(num):
    try:
        mutate(num,offline_all=True,refresh_results=False)
        return dict(id=num,completed=True)
    except Exception as exc:
        # Keep failures visible; no candidate is silently counted as exercised.
        return dict(id=num,completed=False,error=type(exc).__name__+': '+str(exc))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--ids',type=int,nargs='*');args=parser.parse_args()
    ids=args.ids or json.loads((HERE/'expanded-mutation-ids.json').read_text())
    assert ids and len(ids)==len(set(ids))
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(one,ids))
    (HERE/('expanded-mutation-rerun-results.json' if args.ids else 'expanded-mutation-results.json')).write_text(json.dumps(results,indent=2))
    write_results();print('Expanded wave complete',results,flush=True)
