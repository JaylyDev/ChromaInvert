"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.RunPhase = void 0;
var RunPhase;
(function (RunPhase) {
    RunPhase[RunPhase["Idle"] = 0] = "Idle";
    RunPhase[RunPhase["Running"] = 1] = "Running";
    RunPhase[RunPhase["Done"] = 2] = "Done";
    RunPhase[RunPhase["Failed"] = 3] = "Failed";
})(RunPhase || (exports.RunPhase = RunPhase = {}));
