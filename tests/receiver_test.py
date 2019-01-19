
import sys
import threading
import unittest2

import mitogen.core
import testlib


def yield_stuff_then_die(sender):
    for x in range(5):
        sender.send(x)
    sender.close()
    return 10


class ConstructorTest(testlib.RouterMixin, testlib.TestCase):
    def test_handle(self):
        recv = mitogen.core.Receiver(self.router)
        self.assertTrue(isinstance(recv.handle, int))
        self.assertTrue(recv.handle > 100)
        self.router.route(
            mitogen.core.Message.pickled(
                'hi',
                dst_id=0,
                handle=recv.handle,
            )
        )
        self.assertEquals('hi', recv.get().unpickle())


class IterationTest(testlib.RouterMixin, testlib.TestCase):
    def test_dead_stops_iteration(self):
        recv = mitogen.core.Receiver(self.router)
        fork = self.router.fork()
        ret = fork.call_async(yield_stuff_then_die, recv.to_sender())
        self.assertEquals(list(range(5)), list(m.unpickle() for m in recv))
        self.assertEquals(10, ret.get().unpickle())


class CloseTest(testlib.RouterMixin, testlib.TestCase):
    def wait(self, latch, wait_recv):
        try:
            latch.put(wait_recv.get())
        except Exception:
            latch.put(sys.exc_info()[1])

    def test_closes_one(self):
        latch = mitogen.core.Latch()
        wait_recv = mitogen.core.Receiver(self.router)
        t = threading.Thread(target=lambda: self.wait(latch, wait_recv))
        t.start()
        wait_recv.close()
        def throw():
            raise latch.get()
        t.join()
        e = self.assertRaises(mitogen.core.ChannelError, throw)
        self.assertEquals(e.args[0], mitogen.core.Receiver.closed_msg)

    def test_closes_all(self):
        latch = mitogen.core.Latch()
        wait_recv = mitogen.core.Receiver(self.router)
        ts = [
            threading.Thread(target=lambda: self.wait(latch, wait_recv))
            for x in range(5)
        ]
        for t in ts:
            t.start()
        wait_recv.close()
        def throw():
            raise latch.get()
        for x in range(5):
            e = self.assertRaises(mitogen.core.ChannelError, throw)
            self.assertEquals(e.args[0], mitogen.core.Receiver.closed_msg)
        for t in ts:
            t.join()


class OnReceiveTest(testlib.RouterMixin, testlib.TestCase):
    # Verify behaviour of _on_receive dead message handling. A dead message
    # should unregister the receiver and wake all threads.

    def wait(self, latch, wait_recv):
        try:
            latch.put(wait_recv.get())
        except Exception:
            latch.put(sys.exc_info()[1])

    def test_sender_closes_one_thread(self):
        latch = mitogen.core.Latch()
        wait_recv = mitogen.core.Receiver(self.router)
        t = threading.Thread(target=lambda: self.wait(latch, wait_recv))
        t.start()
        sender = wait_recv.to_sender()
        sender.close()
        def throw():
            raise latch.get()
        t.join()
        e = self.assertRaises(mitogen.core.ChannelError, throw)
        self.assertEquals(e.args[0], sender.explicit_close_msg)

    @unittest2.skip(reason=(
        'Unclear if a asingle dead message received from remote should '
        'cause all threads to wake up.'
    ))
    def test_sender_closes_all_threads(self):
        latch = mitogen.core.Latch()
        wait_recv = mitogen.core.Receiver(self.router)
        ts = [
            threading.Thread(target=lambda: self.wait(latch, wait_recv))
            for x in range(5)
        ]
        for t in ts:
            t.start()
        sender = wait_recv.to_sender()
        sender.close()
        def throw():
            raise latch.get()
        for x in range(5):
            e = self.assertRaises(mitogen.core.ChannelError, throw)
            self.assertEquals(e.args[0], mitogen.core.Receiver.closed_msg)
        for t in ts:
            t.join()

    # TODO: what happens to a Select subscribed to the receiver in this case?


if __name__ == '__main__':
    unittest2.main()
