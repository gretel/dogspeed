# asyntest.py Test/demo of the 'micro' Event, Barrier and Semaphore classes
# Test/demo of official asyncio library and official Lock class

# Copyright (c) 2017-2022 Peter Hinch
# Released under the MIT License (MIT) - see LICENSE file

# CPython 3.8 compatibility
# (ignore RuntimeWarning: coroutine '_g' was never awaited)
# To run:
# from primitives.tests.asyntest import test

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio
import sys
unix = "linux" in sys.implementation._machine

from primitives import Barrier, Semaphore, BoundedSemaphore, Condition, Queue, RingbufQueue
try:
    from primitives import Message
except:
    pass

def print_tests():
    st = '''Available functions:
test(0)  Print this list.
test(1)  Test message acknowledge.
test(2)  Test Message and Lock objects.
test(3)  Test the Barrier class with callback.
test(4)  Test the Barrier class with coroutine.
test(5)  Test Semaphore
test(6)  Test BoundedSemaphore.
test(7)  Test the Condition class.
test(8)  Test the Queue class.
test(9)  Test the RingbufQueue class.
'''
    print('\x1b[32m')
    print(st)
    print('\x1b[39m')

print_tests()

def printexp(exp, runtime=0):
    print('Expected output:')
    print('\x1b[32m')
    print(exp)
    print('\x1b[39m')
    if runtime:
        print('Running (runtime = {}s):'.format(runtime))
    else:
        print('Running (runtime < 1s):')

# ************ Test Message class ************
# Demo use of acknowledge message

async def message_wait(message, ack_message, n):
    try:
        await message
        print(f'message_wait {n} got message: {message.value()}')
        if ack_message is not None:
            ack_message.set()
    except asyncio.CancelledError:
        print(f"message_wait {n} cancelled")

async def run_ack(n):
    message = Message()
    ack1 = Message()
    ack2 = Message()
    for count in range(n):
        t0 = asyncio.create_task(message_wait(message, ack1, 1))
        t1 = asyncio.create_task(message_wait(message, ack2, 2))
        message.set(count)
        print('message was set')
        await ack1
        ack1.clear()
        print('Cleared ack1')
        await ack2
        ack2.clear()
        print('Cleared ack2')
        message.clear()
        print('Cleared message')
        await asyncio.sleep(1)
    t0.cancel()
    t1.cancel()

async def msg_send(msg, items):
    for item in items:
        await asyncio.sleep_ms(400)
        msg.set(item)

async def msg_recv(msg):  # Receive using asynchronous iterator
    async for data in msg:
        print("Got", data)
        msg.clear()

async def ack_coro():
    print("Test multiple tasks waiting on a message.")
    await run_ack(3)
    print()
    print("Test asynchronous iterator.")
    msg = Message()
    asyncio.create_task(msg_send(msg, (1, 2, 3)))
    try:
        await asyncio.wait_for(msg_recv(msg), 3)
    except asyncio.TimeoutError:
        pass
    await asyncio.sleep(1)
    print()
    print("Test cancellation of first waiting task.")
    t1 = asyncio.create_task(message_wait(msg, None, 1))
    t2 = asyncio.create_task(message_wait(msg, None, 2))
    await asyncio.sleep(1)
    t1.cancel()
    await asyncio.sleep(1)
    print("Setting message")
    msg.set("Test message")
    await asyncio.sleep(1)  # Tasks have ended or been cancelled
    msg.clear()
    print()
    print("Test cancellation of second waiting task.")
    t1 = asyncio.create_task(message_wait(msg, None, 1))
    t2 = asyncio.create_task(message_wait(msg, None, 2))
    await asyncio.sleep(1)
    t2.cancel()
    await asyncio.sleep(1)
    print("Setting message")
    msg.set("Test message")
    await asyncio.sleep(1)
    msg.clear()

    print("I've seen attack ships burn on the shoulder of Orion...")
    print("Time to die...")

def ack_test():
    if unix:
        print("Message class is incompatible with Unix build.")
        return
    printexp('''Running (runtime = 12s):
Test multiple tasks waiting on a message.
message was set
message_wait 1 got message: 0
message_wait 2 got message: 0
Cleared ack1
Cleared ack2
Cleared message
message was set
message_wait 1 got message: 1
message_wait 2 got message: 1
Cleared ack1
Cleared ack2
Cleared message
message was set
message_wait 1 got message: 2
message_wait 2 got message: 2
Cleared ack1
Cleared ack2
Cleared message

Test asynchronous iterator.
Got 1
Got 2
Got 3

Test cancellation of first waiting task.
message_wait 1 cancelled
Setting message
message_wait 2 got message: Test message

Test cancellation of second waiting task.
message_wait 2 cancelled
Setting message
message_wait 1 got message: Test message
I've seen attack ships burn on the shoulder of Orion...
Time to die...
''', 12)
    asyncio.run(ack_coro())

# ************ Test Lock and Message classes ************

async def run_lock(n, lock):
    print('run_lock {} waiting for lock'.format(n))
    await lock.acquire()
    print('run_lock {} acquired lock'.format(n))
    await asyncio.sleep(1)  # Delay to demo other coros waiting for lock
    lock.release()
    print('run_lock {} released lock'.format(n))

async def messageset(message):
    print('Waiting 5 secs before setting message')
    await asyncio.sleep(5)
    message.set()
    print('message was set')

async def messagewait(message):
    print('waiting for message')
    await message
    print('got message')
    message.clear()

async def run_message_test():
    print('Test Lock class')
    lock = asyncio.Lock()
    asyncio.create_task(run_lock(1, lock))
    asyncio.create_task(run_lock(2, lock))
    asyncio.create_task(run_lock(3, lock))
    print('Test Message class')
    message = Message()
    asyncio.create_task(messageset(message))
    await messagewait(message)  # run_message_test runs fast until this point
    print('Message status {}'.format('Incorrect' if message.is_set() else 'OK'))
    print('Tasks complete')

def msg_test():
    if unix:
        print("Message class is incompatible with Unix build.")
        return
    printexp('''Test Lock class
Test Message class
waiting for message
run_lock 1 waiting for lock
run_lock 1 acquired lock
run_lock 2 waiting for lock
run_lock 3 waiting for lock
Waiting 5 secs before setting message
run_lock 1 released lock
run_lock 2 acquired lock
run_lock 2 released lock
run_lock 3 acquired lock
run_lock 3 released lock
message was set
got message
Message status OK
Tasks complete
''', 5)
    asyncio.run(run_message_test())

# ************ Barrier test ************

async def killer(duration):
    await asyncio.sleep(duration)

def callback(text):
    print(text)

async def report(barrier):
    for i in range(5):
        print('{} '.format(i), end='')
        await barrier

async def do_barrier_test():
    barrier = Barrier(3, callback, ('Synch',))
    for _ in range(2):
        for _ in range(3):
            asyncio.create_task(report(barrier))
        await asyncio.sleep(1)
        print()
    await asyncio.sleep(1)

def barrier_test():
    printexp('''Running (runtime = 3s):
0 0 0 Synch
1 1 1 Synch
2 2 2 Synch
3 3 3 Synch
4 4 4 Synch

1 1 1 Synch
2 2 2 Synch
3 3 3 Synch
4 4 4 Synch
''', 3)
    asyncio.run(do_barrier_test())

# ************ Barrier test 1 ************

async def my_coro(text):
    try:
        await asyncio.sleep_ms(0)
        while True:
            await asyncio.sleep(1)
            print(text)
    except asyncio.CancelledError:
        print('my_coro was cancelled.')

async def report1(barrier, x):
    await asyncio.sleep(x)
    print('report instance', x, 'waiting')
    await barrier
    print('report instance', x, 'done')

async def bart():
    barrier = Barrier(4, my_coro, ('my_coro running',))
    for x in range(3):
        asyncio.create_task(report1(barrier, x))
    await asyncio.sleep(4)
    assert barrier.busy()
    await barrier
    await asyncio.sleep(0)
    assert not barrier.busy()
    # Must yield before reading result(). Here we wait long enough for
    await asyncio.sleep_ms(1500)  # coro to print
    barrier.result().cancel()
    await asyncio.sleep(2)

def barrier_test1():
    printexp('''Running (runtime = 5s):
report instance 0 waiting
report instance 1 waiting
report instance 2 waiting
report instance 2 done
report instance 1 done
report instance 0 done
my_coro running
my_coro was cancelled.

Exact report instance done sequence may vary, but 3 instances should report
done before my_coro runs.
''', 5)
    asyncio.run(bart())

# ************ Semaphore test ************

async def run_sema(n, sema, barrier):
    print('run_sema {} trying to access semaphore'.format(n))
    async with sema:
        print('run_sema {} acquired semaphore'.format(n))
        # Delay demonstrates other coros waiting for semaphore
        await asyncio.sleep(1 + n/10)  # n/10 ensures deterministic printout
    print('run_sema {} has released semaphore'.format(n))
    barrier.trigger()

async def run_sema_test(bounded):
    num_coros = 5
    barrier = Barrier(num_coros + 1)
    if bounded:
        semaphore = BoundedSemaphore(3)
    else:
        semaphore = Semaphore(3)
    for n in range(num_coros):
        asyncio.create_task(run_sema(n, semaphore, barrier))
    await barrier  # Quit when all coros complete
    try:
        semaphore.release()
    except ValueError:
        print('Bounded semaphore exception test OK')

def semaphore_test(bounded=False):
    if bounded:
        exp = '''run_sema 0 trying to access semaphore
run_sema 0 acquired semaphore
run_sema 1 trying to access semaphore
run_sema 1 acquired semaphore
run_sema 2 trying to access semaphore
run_sema 2 acquired semaphore
run_sema 3 trying to access semaphore
run_sema 4 trying to access semaphore
run_sema 0 has released semaphore
run_sema 4 acquired semaphore
run_sema 1 has released semaphore
run_sema 3 acquired semaphore
run_sema 2 has released semaphore
run_sema 4 has released semaphore
run_sema 3 has released semaphore
Bounded semaphore exception test OK

Exact sequence of acquisition may vary when 3 and 4 compete for semaphore.'''
    else:
        exp = '''run_sema 0 trying to access semaphore
run_sema 0 acquired semaphore
run_sema 1 trying to access semaphore
run_sema 1 acquired semaphore
run_sema 2 trying to access semaphore
run_sema 2 acquired semaphore
run_sema 3 trying to access semaphore
run_sema 4 trying to access semaphore
run_sema 0 has released semaphore
run_sema 3 acquired semaphore
run_sema 1 has released semaphore
run_sema 4 acquired semaphore
run_sema 2 has released semaphore
run_sema 3 has released semaphore
run_sema 4 has released semaphore

Exact sequence of acquisition may vary when 3 and 4 compete for semaphore.'''
    printexp(exp, 3)
    asyncio.run(run_sema_test(bounded))

# ************ Condition test ************

cond = Condition()
tim = 0

async def cond01():
    while True:
        await asyncio.sleep(2)
        with await cond:
            cond.notify(2)  # Notify 2 tasks

async def cond03():  # Maintain a count of seconds
    global tim
    await asyncio.sleep(0.5)
    while True:
        await asyncio.sleep(1)
        tim += 1

async def cond02(n, barrier):
    with await cond:
        print('cond02', n, 'Awaiting notification.')
        await cond.wait()
        print('cond02', n, 'triggered. tim =', tim)
        barrier.trigger()

def predicate():
    return tim >= 8 # 12

async def cond04(n, barrier):
    with await cond:
        print('cond04', n, 'Awaiting notification and predicate.')
        await cond.wait_for(predicate)
        print('cond04', n, 'triggered. tim =', tim)
        barrier.trigger()

async def cond_go():
    ntasks = 7
    barrier = Barrier(ntasks + 1)
    t1 = asyncio.create_task(cond01())
    t3 = asyncio.create_task(cond03())
    for n in range(ntasks):
        asyncio.create_task(cond02(n, barrier))
    await barrier  # All instances of cond02 have completed
    # Test wait_for
    barrier = Barrier(2)
    asyncio.create_task(cond04(99, barrier))
    await barrier
    # cancel continuously running coros.
    t1.cancel()
    t3.cancel()
    await asyncio.sleep_ms(0)
    print('Done.')

def condition_test():
    printexp('''cond02 0 Awaiting notification.
cond02 1 Awaiting notification.
cond02 2 Awaiting notification.
cond02 3 Awaiting notification.
cond02 4 Awaiting notification.
cond02 5 Awaiting notification.
cond02 6 Awaiting notification.
cond02 5 triggered. tim = 1
cond02 6 triggered. tim = 1
cond02 3 triggered. tim = 3
cond02 4 triggered. tim = 3
cond02 1 triggered. tim = 5
cond02 2 triggered. tim = 5
cond02 0 triggered. tim = 7
cond04 99 Awaiting notification and predicate.
cond04 99 triggered. tim = 9
Done.
''', 13)
    asyncio.run(cond_go())

# ************ Queue test ************

async def slow_process():
    await asyncio.sleep(2)
    return 42

async def bar(q):
    print('Waiting for slow process.')
    result = await slow_process()
    print('Putting result onto queue')
    await q.put(result)  # Put result on q

async def foo(q):
    print("Running foo()")
    result = await q.get()
    print('Result was {}'.format(result))

async def q_put(n, q):
    for x in range(8):
        obj = (n, x)
        await q.put(obj)
        await asyncio.sleep(0)

async def q_get(n, q):
    for x in range(8):
        await q.get()
        await asyncio.sleep(0)

async def putter(q):
    # put some item, then sleep
    for _ in range(20):
        await q.put(1)
        await asyncio.sleep_ms(50)


async def getter(q):
   # checks for new items, and relies on the "blocking" of the get method
    for _ in range(20):
        await q.get()

async def queue_go():
    q = Queue(10)
    asyncio.create_task(foo(q))
    asyncio.create_task(bar(q))
    await asyncio.sleep(3)
    for n in range(4):
        asyncio.create_task(q_put(n, q))
    await asyncio.sleep(1)
    assert q.qsize() == 10
    await q.get()
    await asyncio.sleep(0.1)
    assert q.qsize() == 10
    while not q.empty():
        await q.get()
        await asyncio.sleep(0.1)
    assert q.empty()
    print('Competing put tasks test complete')

    for n in range(4):
        asyncio.create_task(q_get(n, q))
    await asyncio.sleep(1)
    x = 0
    while not q.full():
        await q.put(x)
        await asyncio.sleep(0.3)
        x += 1
    assert q.qsize() == 10
    print('Competing get tasks test complete')
    await asyncio.gather(
        putter(q),
        getter(q)
        )
    print('Queue tests complete')
    print("I've seen attack ships burn off the shoulder of Orion...")
    print("Time to die...")

def queue_test():
    printexp('''Running (runtime = 20s):
Running foo()
Waiting for slow process.
Putting result onto queue
Result was 42
Competing put tasks test complete
Competing get tasks test complete
Queue tests complete


I've seen attack ships burn off the shoulder of Orion...
Time to die...

''', 20)
    asyncio.run(queue_go())

# ************ RingbufQueue test ************

async def qread(q, lst, twr):
    async for item in q:
        lst.append(item)
        await asyncio.sleep_ms(twr)

async def read(q, t, twr=0):
    lst = []
    try:
        await asyncio.wait_for(qread(q, lst, twr), t)
    except asyncio.TimeoutError:
        pass
    return lst

async def put_list(q, lst, twp=0):
    for item in lst:
        await q.put(item)
        await asyncio.sleep_ms(twp)

async def rbq_go():
    q = RingbufQueue([0 for _ in range(10)])  # 10 elements
    pl = [n for n in range(15)]
    print("Read waits on slow write.")
    asyncio.create_task(put_list(q, pl, 100))
    rl = await read(q, 2)
    assert pl == rl
    print('done')
    print("Write waits on slow read.")
    asyncio.create_task(put_list(q, pl))
    rl = await read(q, 2, 100)
    assert pl == rl
    print('done')
    print("Testing full, empty and qsize methods.")
    assert q.empty()
    assert q.qsize() == 0
    assert not q.full()
    await put_list(q, (1,2,3))
    assert not q.empty()
    assert q.qsize() == 3
    assert not q.full()
    print("Done")
    print("Testing put_nowait and overruns.")
    nfail = 0
    for x in range(4, 15):
        try:
            q.put_nowait(x)
        except IndexError:
            nfail += 1
    assert nfail == 5
    assert q.full()
    rl = await read(q, 2)
    assert rl == [6, 7, 8, 9, 10, 11, 12, 13, 14]
    print("Testing get_nowait.")
    await q.put(1)
    assert q.get_nowait() == 1
    err = 0
    try:
        q.get_nowait()
    except IndexError:
        err = 1
    assert err == 1
    print("Tests complete.")
    print("I've seen attack ships burn off the shoulder of Orion...")
    print("Time to die...")

def rbq_test():
    printexp('''Running (runtime = 6s):
Read waits on slow write.
done
Write waits on slow read.
done
Testing full, empty and qsize methods.
Done
Testing put_nowait and overruns.
Testing get_nowait.
Tests complete.
I've seen attack ships burn off the shoulder of Orion...
Time to die...

''', 6)
    asyncio.run(rbq_go())

# ************ ************
def test(n):
    try:
        if n == 1:
            ack_test()  # Test message acknowledge.
        elif n == 2:
            msg_test()  # Test Messge and Lock objects.
        elif n == 3:
            barrier_test()  # Test the Barrier class.
        elif n == 4:
            barrier_test1()  # Test the Barrier class.
        elif n == 5:
            semaphore_test(False) # Test Semaphore
        elif n == 6:
            semaphore_test(True)  # Test BoundedSemaphore.
        elif n == 7:
            condition_test()  # Test the Condition class.
        elif n == 8:
            queue_test()  # Test the Queue class.
        elif n == 9:
            rbq_test()  # Test the RingbufQueue class.
    except KeyboardInterrupt:
        print('Interrupted')
    finally:
        asyncio.new_event_loop()
        print_tests()
