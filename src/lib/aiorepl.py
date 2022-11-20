# https://raw.githubusercontent.com/micropython/micropython-lib/master/micropython/aiorepl/aiorepl.py
# MIT license; Copyright (c) 2022 Jim Mussared
_B=True
_A=None
import micropython,re,sys,time,uasyncio as asyncio
_RE_IMPORT=re.compile('^import ([^ ]+)( as ([^ ]+))?')
_RE_FROM_IMPORT=re.compile('^from [^ ]+ import ([^ ]+)( as ([^ ]+))?')
_RE_GLOBAL=re.compile('^([a-zA-Z0-9_]+) ?=[^=]')
_RE_ASSIGN=re.compile('[^=]=[^=]')
_HISTORY_LIMIT=const(5+1)
async def execute(code,g,s):
    A='__exec_task'
    if not code.strip():return
    try:
        if'await 'in code:
            if(m:=_RE_IMPORT.match(code)or _RE_FROM_IMPORT.match(code)):code=f"global {m.group(3)or m.group(1)}\n    {code}"
            elif(m:=_RE_GLOBAL.match(code)):code=f"global {m.group(1)}\n    {code}"
            elif not _RE_ASSIGN.search(code):code=f"return {code}"
            code=f"""
import uasyncio as asyncio
async def __code():
    {code}

__exec_task = asyncio.create_task(__code())
"""
            async def kbd_intr_task(exec_task,s):
                while _B:
                    if ord(await s.read(1))==3:exec_task.cancel();return
            l={A:_A};exec(code,g,l);exec_task=l[A];intr_task=asyncio.create_task(kbd_intr_task(exec_task,s))
            try:
                try:return await exec_task
                except asyncio.CancelledError:pass
            finally:
                intr_task.cancel()
                try:await intr_task
                except asyncio.CancelledError:pass
        else:
            try:
                try:
                    micropython.kbd_intr(3)
                    try:return eval(code,g)
                    except SyntaxError:return exec(code,g)
                except KeyboardInterrupt:pass
            finally:micropython.kbd_intr(-1)
    except Exception as err:print(f"{type(err).__name__}: {err}")
async def task(g=_A,prompt='--> '):
    B='[A';A='\n';print('Starting asyncio REPL...')
    if g is _A:g=__import__('__main__').__dict__
    try:
        micropython.kbd_intr(-1);s=asyncio.StreamReader(sys.stdin);hist=[_A]*_HISTORY_LIMIT;hist_i=0;hist_n=0;c=0;t=0
        while _B:
            hist_b=0;sys.stdout.write(prompt);cmd=''
            while _B:
                b=await s.read(1);pc=c;c=ord(b);pt=t;t=time.ticks_ms()
                if c<32 or c>126:
                    if c==10:
                        if pc==10 and time.ticks_diff(t,pt)<20:continue
                        sys.stdout.write(A)
                        if cmd:
                            hist[hist_i]=cmd;hist_n=min(_HISTORY_LIMIT-1,hist_n+1);hist_i=(hist_i+1)%_HISTORY_LIMIT;result=await execute(cmd,g,s)
                            if result is not _A:sys.stdout.write(repr(result));sys.stdout.write(A)
                        break
                    elif c==8 or c==127:
                        if cmd:cmd=cmd[:-1];sys.stdout.write('\x08 \x08')
                    elif c==2:continue
                    elif c==3:
                        if pc==3 and time.ticks_diff(t,pt)<20:asyncio.new_event_loop();return
                        sys.stdout.write(A);break
                    elif c==4:sys.stdout.write(A);asyncio.new_event_loop();return
                    elif c==27:
                        key=await s.read(2)
                        if key in(B,'[B'):
                            hist[(hist_i-hist_b)%_HISTORY_LIMIT]=cmd;b='\x08'*len(cmd);sys.stdout.write(b);sys.stdout.write(' '*len(cmd));sys.stdout.write(b)
                            if key==B:hist_b=min(hist_n,hist_b+1)
                            else:hist_b=max(0,hist_b-1)
                            cmd=hist[(hist_i-hist_b)%_HISTORY_LIMIT];sys.stdout.write(cmd)
                    else:0
                else:sys.stdout.write(b);cmd+=b
    finally:micropython.kbd_intr(3)