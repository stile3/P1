package flash.system {
    import flash.display.Loader;
    import flash.events.Event;
    import flash.events.EventDispatcher;
    import flash.events.IOErrorEvent;
    import flash.events.SecurityErrorEvent;
    import flash.system.ApplicationDomain;
    import flash.system.LoaderContext;
    import flash.system.MessageChannel;
    import flash.utils.ByteArray;
    import flash.utils.Timer;
    import flash.events.TimerEvent;

    [API("682")]
    [Ruffle(Abstract)]
    public final class Worker extends EventDispatcher {
        private static var _primordial:Worker;
        private static var _current:Worker;
        private static var _active:Worker;
        private static var _queue:Array = [];

        // Vicalox V11 Turbo:
        // Real Flash ran each Worker on another thread. Ruffle currently runs our
        // compatibility workers inside the same AVM2 thread. Running two separate
        // 30 FPS timers therefore causes two expensive worker bursts on top of the
        // 30 FPS render loop. Use one 30 Hz scheduler and alternate workers. With
        // two MU workers each worker receives 15 ENTER_FRAME ticks/sec, while the
        // main game keeps its original 30 FPS render rate.
        private static var _runningWorkers:Array = [];
        private static var _scheduler:Timer;
        private static var _schedulerCursor:int = 0;

        private var _swf:ByteArray;
        private var _shared:Object;
        private var _state:String;
        private var _loader:Loader;

        public static function get isSupported():Boolean {
            return true;
        }

        private static function ensurePrimordial():Worker {
            if (!_primordial) {
                _primordial = instantiateInternal();
                _primordial._state = WorkerState.RUNNING;
            }
            return _primordial;
        }

        public static function get current():Worker {
            if (_current) {
                return _current;
            }
            return ensurePrimordial();
        }

        internal static function createFromBytes(swf:ByteArray):Worker {
            var worker:Worker = instantiateInternal();
            worker._swf = swf;
            worker._shared = {};
            worker._state = WorkerState.NEW;
            return worker;
        }

        public function get state():String {
            if (!_state) {
                return WorkerState.NEW;
            }
            return _state;
        }

        public native function createMessageChannel(receiver:Worker):MessageChannel;

        public function setSharedProperty(key:String, value:*):void {
            if (!_shared) {
                _shared = {};
            }
            _shared[key] = value;
        }

        public function getSharedProperty(key:String):* {
            if (!_shared) {
                return undefined;
            }
            return _shared[key];
        }

        public function start():void {
            if (_state == WorkerState.RUNNING) {
                return;
            }
            if (!_swf) {
                _state = WorkerState.TERMINATED;
                dispatchEvent(new Event(Event.WORKER_STATE));
                return;
            }

            _queue.push(this);
            pumpQueue();
        }

        private static function pumpQueue():void {
            if (_active || _queue.length == 0) {
                return;
            }

            ensurePrimordial();

            var worker:Worker = _queue.shift() as Worker;
            _active = worker;
            _current = worker;
            worker.beginLoad();
        }

        private function beginLoad():void {
            _loader = new Loader();
            _loader.contentLoaderInfo.addEventListener(Event.COMPLETE, workerComplete);
            _loader.contentLoaderInfo.addEventListener(IOErrorEvent.IO_ERROR, workerError);
            _loader.contentLoaderInfo.addEventListener(SecurityErrorEvent.SECURITY_ERROR, workerError);

            var domain:ApplicationDomain = new ApplicationDomain(ApplicationDomain.currentDomain);
            var context:LoaderContext = new LoaderContext(false, domain);
            _loader.loadBytes(_swf, context);
        }

        private function workerComplete(event:Event):void {
            cleanupLoaderListeners();
            _state = WorkerState.RUNNING;

            _runningWorkers.push(this);
            ensureScheduler();

            _current = ensurePrimordial();
            dispatchEvent(new Event(Event.WORKER_STATE));

            _active = null;
            pumpQueue();
        }

        private static function ensureScheduler():void {
            if (_scheduler) {
                return;
            }
            _scheduler = new Timer(1000.0 / 30.0);
            _scheduler.addEventListener(TimerEvent.TIMER, schedulerTick);
            _scheduler.start();
        }

        private static function schedulerTick(event:TimerEvent):void {
            if (_runningWorkers.length == 0) {
                return;
            }
            if (_schedulerCursor >= _runningWorkers.length) {
                _schedulerCursor = 0;
            }

            var worker:Worker = _runningWorkers[_schedulerCursor] as Worker;
            _schedulerCursor++;
            if (_schedulerCursor >= _runningWorkers.length) {
                _schedulerCursor = 0;
            }

            if (worker) {
                _current = worker;
                try {
                    worker.tickOnce();
                } finally {
                    _current = ensurePrimordial();
                }
            }
        }

        private function tickOnce():void {
            if (_loader && _loader.content && _state == WorkerState.RUNNING) {
                _loader.content.dispatchEvent(new Event(Event.ENTER_FRAME));
            }
        }

        private function workerError(event:Event):void {
            cleanupLoaderListeners();
            _state = WorkerState.TERMINATED;
            _current = ensurePrimordial();
            dispatchEvent(new Event(Event.WORKER_STATE));
            _active = null;
            pumpQueue();
        }

        private function cleanupLoaderListeners():void {
            if (!_loader) {
                return;
            }
            _loader.contentLoaderInfo.removeEventListener(Event.COMPLETE, workerComplete);
            _loader.contentLoaderInfo.removeEventListener(IOErrorEvent.IO_ERROR, workerError);
            _loader.contentLoaderInfo.removeEventListener(SecurityErrorEvent.SECURITY_ERROR, workerError);
        }

        private static native function instantiateInternal():Worker;
    }
}
