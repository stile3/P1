package flash.system {
    import flash.utils.ByteArray;

    [API("680")]
    [Ruffle(Abstract)]
    public final class WorkerDomain {
        private static var _current:WorkerDomain;

        public static function get isSupported():Boolean {
            return true;
        }

        public static function get current():WorkerDomain {
            if (!_current) {
                _current = instantiateInternal();
            }
            return _current;
        }

        public function createWorker(swf:ByteArray, giveAppPrivileges:Boolean = false):Worker {
            return Worker.createFromBytes(swf);
        }

        private static native function instantiateInternal():WorkerDomain;
    }
}
