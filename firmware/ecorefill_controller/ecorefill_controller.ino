#include <Arduino.h>
#include <ESP32Servo.h>
#include <driver/gpio.h>
#include <ctype.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

// EcoRefill: newline-delimited commands at 115200 baud.
// All operation timers use unsigned subtraction, including across millis wrap.
constexpr int GATE_SERVO_PIN = 19, SORT_SERVO_PIN = 18;
constexpr int RELAY1 = 5, RELAY2 = 23, TRIG_PIN = 32, ECHO_PIN = 33;
constexpr int RELAY_ON = LOW, RELAY_OFF = HIGH;
constexpr int GATE_CENTER = 90, GATE_ACCEPT = 0, GATE_REJECT = 180;
constexpr int SORT_CENTER = 90, SORT_BOTTLE = 0, SORT_CAN = 180;
constexpr uint32_t MOVE_DELAY = 700, DROP_DELAY = 1500;
// Retained from the supplied sketch. These are 25, 30 and 45 SECONDS.
// Measure each volume on the actual machine; these are not verified mL values.
constexpr uint32_t WATER_250_TIME = 25000, WATER_500_TIME = 30000;
constexpr uint32_t WATER_1000_TIME = 45000;
constexpr uint32_t BOTTLE_WAIT_TIMEOUT = 30000;
constexpr uint32_t SENSOR_INTERVAL = 100, ECHO_TIMEOUT_US = 30000;
constexpr uint32_t CONTAINER_LOSS_TIMEOUT = 600;
constexpr uint32_t REMOVAL_CONFIRM_TIME = 1000;
constexpr float TRIGGER_DISTANCE_CM = 10.0f, REMOVE_DISTANCE_CM = 14.0f;
constexpr unsigned REQUIRED_BOTTLE_READINGS = 2;
constexpr uint32_t COMMAND_TIMEOUT = 1000;

Servo gateServo, sortServo;
enum class State { IDLE, WAIT_BOTTLE, DISPENSING, SORT_MOVE, GATE_DROP,
                   GATE_CLOSE, SORT_CENTERING, RESETTING };
State state = State::RESETTING;
uint32_t stateStarted = 0, lastSensorAt = 0, lastPresentAt = 0;
uint32_t waterDuration = 0, absenceStarted = 0;
unsigned bottleReadings = 0;
bool waterNeedsRemoval = false, trackingAbsence = false, servoReady = false;
bool sensorMissing = false;
const char *activeCommand = nullptr;

// Fixed memory for input and output. Never wait for a newline or serial reader.
char commandBuffer[32];
size_t commandLength = 0;
uint32_t commandStarted = 0;
bool discardingCommand = false;
constexpr size_t TX_SLOTS = 16, TX_LINE_SIZE = 80;
char txLines[TX_SLOTS][TX_LINE_SIZE];
size_t txHead = 0, txCount = 0, txOffset = 0;

// Explicit declarations keep Arduino's generated prototypes from appearing
// before the State enum. Defaults are supplied on the definitions below.
uint32_t elapsed(uint32_t now, uint32_t then);
void sendLine(const char *prefix, const char *command, const char *reason, bool critical);
void serviceOutput();
void pumpsOff();
void enterState(State next, uint32_t now);
float getDistance();
void finishWater(const char *error);
void resetSystem();
void handleCommand(char *command);
void serviceInput();
void serviceOperation();
void setup();
void loop();

uint32_t elapsed(uint32_t now, uint32_t then) { return now - then; }

void sendLine(const char *prefix, const char *command = "",
              const char *reason = "", bool critical = false) {
  // Reserve space for final responses. Under a sustained flood, discard new
  // replies instead of blocking control or corrupting a partially sent line.
  if (txCount >= TX_SLOTS || (!critical && txCount >= TX_SLOTS - 4)) return;
  size_t tail = (txHead + txCount) % TX_SLOTS;
  snprintf(txLines[tail], TX_LINE_SIZE, "%s%s%s%s%s\n", prefix,
           *command ? " " : "", command, *reason ? " " : "", reason);
  ++txCount;
}

void serviceOutput() {
  if (!txCount) return;
  int room = Serial.availableForWrite();
  if (room <= 0) return;
  size_t remaining = strlen(txLines[txHead]) - txOffset;
  size_t count = remaining < 32 ? remaining : 32;
  if (count > static_cast<size_t>(room)) count = room;
  txOffset += Serial.write(
    reinterpret_cast<const uint8_t *>(txLines[txHead] + txOffset), count);
  if (txOffset == strlen(txLines[txHead])) {
    txOffset = 0;
    txHead = (txHead + 1) % TX_SLOTS;
    --txCount;
  }
}

void pumpsOff() {
  digitalWrite(RELAY1, RELAY_OFF);
  digitalWrite(RELAY2, RELAY_OFF);
}

void enterState(State next, uint32_t now) {
  state = next;
  stateStarted = now;
}

float getDistance() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  unsigned long duration = pulseIn(ECHO_PIN, HIGH, ECHO_TIMEOUT_US);
  return duration ? duration * 0.0343f / 2.0f : -1.0f;
}

void finishWater(const char *error = nullptr) {
  pumpsOff();  // Physical shutdown always precedes serial reporting.
  if (error) sendLine("ERROR", activeCommand, error, true);
  else sendLine("OK", activeCommand, "", true);
  activeCommand = nullptr;
  trackingAbsence = false;
  enterState(State::IDLE, millis());
}

void resetSystem() {
  pumpsOff();
  if (activeCommand) sendLine("ERROR", activeCommand, "CANCELLED", true);
  activeCommand = nullptr;
  gateServo.write(GATE_CENTER);
  sortServo.write(SORT_CENTER);
  bottleReadings = 0;
  trackingAbsence = false;
  // Do not clear the removal latch: RESET must not re-arm a bottle just filled.
  enterState(State::RESETTING, millis());
}

void handleCommand(char *command) {
  while (*command && isspace(static_cast<unsigned char>(*command))) ++command;
  size_t length = strlen(command);
  while (length && isspace(static_cast<unsigned char>(command[length - 1])))
    command[--length] = '\0';
  for (size_t i = 0; i < length; ++i)
    command[i] = toupper(static_cast<unsigned char>(command[i]));
  if (!length) return;
  if (!strcmp(command, "RESET")) { resetSystem(); return; }

  const char *recognized = nullptr;
  uint32_t duration = 0;
  if (!strcmp(command, "WATER_250")) {
    recognized = "WATER_250"; duration = WATER_250_TIME;
  } else if (!strcmp(command, "WATER_500")) {
    recognized = "WATER_500"; duration = WATER_500_TIME;
  } else if (!strcmp(command, "WATER_1000")) {
    recognized = "WATER_1000"; duration = WATER_1000_TIME;
  } else if (!strcmp(command, "BOTTLE")) recognized = "BOTTLE";
  else if (!strcmp(command, "CAN")) recognized = "CAN";
  else if (!strcmp(command, "REJECT")) recognized = "REJECT";
  if (!recognized) { sendLine("UNKNOWN COMMAND:", command); return; }

  if (state != State::IDLE) {
    // A retransmission of the active water request reports its existing state;
    // it must neither queue another refill nor fail the original Pi request.
    if (duration && activeCommand && !strcmp(command, activeCommand)) {
      if (state == State::DISPENSING) sendLine("DISPENSING", activeCommand);
      else sendLine("WAITING FOR BOTTLE");
    } else sendLine("ERROR", recognized, "BUSY");
    return;
  }
  if (duration && waterNeedsRemoval) {
    sendLine("ERROR", recognized, "REMOVE_CONTAINER"); return;
  }
  if (!duration && !servoReady) {
    sendLine("ERROR", recognized, "SERVO_UNAVAILABLE"); return;
  }
  // Do not start physical work when its response cannot be queued.
  if (txCount >= TX_SLOTS - 4) return;
  activeCommand = recognized;
  trackingAbsence = false;
  uint32_t now = millis();
  if (duration) {
    pumpsOff();
    waterDuration = duration;
    bottleReadings = 0;
    lastSensorAt = now - SENSOR_INTERVAL;
    enterState(State::WAIT_BOTTLE, now);
    sendLine("WATER REQUEST", activeCommand);
    sendLine("WAITING FOR BOTTLE");
  } else if (!strcmp(command, "REJECT")) {
    gateServo.write(GATE_REJECT);
    enterState(State::GATE_DROP, now);
    sendLine("REJECTING ITEM");
  } else {
    sortServo.write(!strcmp(command, "BOTTLE") ? SORT_BOTTLE : SORT_CAN);
    enterState(State::SORT_MOVE, now);
    sendLine("MOVING", activeCommand);
  }
}

void serviceInput() {
  if (commandLength && elapsed(millis(), commandStarted) >= COMMAND_TIMEOUT) {
    commandLength = 0;
    discardingCommand = true;
    sendLine("ERROR SERIAL LINE_TIMEOUT");
  }
  // Bound work even if the sender never stops transmitting.
  for (unsigned budget = 0; budget < 32 && Serial.available() > 0; ++budget) {
    int value = Serial.read();
    if (value < 0) break;
    char c = static_cast<char>(value);
    if (c == '\n') {
      if (!discardingCommand) {
        commandBuffer[commandLength] = '\0';
        handleCommand(commandBuffer);
      }
      commandLength = 0;
      discardingCommand = false;
    } else if (!discardingCommand) {
      if ((static_cast<unsigned char>(c) < 32 && c != '\r' && c != '\t') ||
          static_cast<unsigned char>(c) > 126) {
        commandLength = 0;
        discardingCommand = true;
        sendLine("ERROR SERIAL INVALID_CHARACTER");
      } else if (commandLength == sizeof(commandBuffer) - 1) {
        commandLength = 0;
        discardingCommand = true;
        sendLine("ERROR SERIAL LINE_TOO_LONG");
      } else {
        if (!commandLength) commandStarted = millis();
        commandBuffer[commandLength++] = c;
      }
    }
  }
}

void serviceOperation() {
  uint32_t now = millis();
  if (state == State::DISPENSING) {
    if (elapsed(now, stateStarted) >= waterDuration) { finishWater(); return; }
    if (elapsed(now, lastPresentAt) >= CONTAINER_LOSS_TIMEOUT) {
      finishWater(sensorMissing ? "SENSOR_LOST" : "CONTAINER_REMOVED"); return;
    }
  }
  if (state == State::WAIT_BOTTLE &&
      elapsed(now, stateStarted) >= BOTTLE_WAIT_TIMEOUT) {
    finishWater("NO_BOTTLE"); return;
  }

  bool needsSensor = state == State::WAIT_BOTTLE || state == State::DISPENSING ||
                     (state == State::IDLE && waterNeedsRemoval);
  if (needsSensor && elapsed(now, lastSensorAt) >= SENSOR_INTERVAL) {
    lastSensorAt = now;
    float distance = getDistance(); // Bounded to 30 ms; recheck deadlines afterward.
    sensorMissing = distance <= 0;
    now = millis();
    if (state == State::WAIT_BOTTLE) {
      if (elapsed(now, stateStarted) >= BOTTLE_WAIT_TIMEOUT) {
        finishWater("NO_BOTTLE"); return;
      }
      if (distance > 0 && distance <= TRIGGER_DISTANCE_CM) ++bottleReadings;
      else bottleReadings = 0;
      if (bottleReadings >= REQUIRED_BOTTLE_READINGS) {
        waterNeedsRemoval = true;
        trackingAbsence = false;
        lastPresentAt = now;
        digitalWrite(RELAY1, RELAY_ON);
        enterState(State::DISPENSING, now);
        sendLine("DISPENSING", activeCommand, "", true);
      }
    } else if (state == State::DISPENSING) {
      if (elapsed(now, stateStarted) >= waterDuration) { finishWater(); return; }
      // Test expiry before accepting a late recovery reading. Far and no-echo
      // readings both consume the SAME grace period, never resetting each other.
      if (elapsed(now, lastPresentAt) >= CONTAINER_LOSS_TIMEOUT) {
        finishWater(distance <= 0 ? "SENSOR_LOST" : "CONTAINER_REMOVED");
        return;
      }
      if (distance > 0 && distance <= REMOVE_DISTANCE_CM) lastPresentAt = now;
    } else {
      // Require a full second of absence after every started refill. No echo
      // counts as absence here only (pump is off), to support an empty backdrop.
      if (distance <= 0 || distance > REMOVE_DISTANCE_CM) {
        if (!trackingAbsence) { trackingAbsence = true; absenceStarted = now; }
        else if (elapsed(now, absenceStarted) >= REMOVAL_CONFIRM_TIME) {
          waterNeedsRemoval = false;
          trackingAbsence = false;
        }
      } else trackingAbsence = false;
    }
  }

  switch (state) {
    case State::SORT_MOVE:
      if (elapsed(now, stateStarted) >= MOVE_DELAY) {
        gateServo.write(GATE_ACCEPT); enterState(State::GATE_DROP, now);
      }
      break;
    case State::GATE_DROP:
      if (elapsed(now, stateStarted) >= DROP_DELAY) {
        gateServo.write(GATE_CENTER); enterState(State::GATE_CLOSE, now);
      }
      break;
    case State::GATE_CLOSE:
      if (elapsed(now, stateStarted) >= MOVE_DELAY) {
        sortServo.write(SORT_CENTER); enterState(State::SORT_CENTERING, now);
      }
      break;
    case State::SORT_CENTERING:
      if (elapsed(now, stateStarted) >= MOVE_DELAY) {
        sendLine("OK", activeCommand, "", true);
        activeCommand = nullptr; enterState(State::IDLE, now);
      }
      break;
    case State::RESETTING:
      if (elapsed(now, stateStarted) >= 1000) {
        sendLine("OK RESET", "", "", true); enterState(State::IDLE, now);
      }
      break;
    default: break;
  }
}

void setup() {
  // Preload output latches with the ESP-IDF API BEFORE enabling output. Recent
  // Arduino cores reject digitalWrite() on pins not yet configured as GPIO.
  gpio_set_level(static_cast<gpio_num_t>(RELAY1), RELAY_OFF);
  gpio_set_level(static_cast<gpio_num_t>(RELAY2), RELAY_OFF);
  pinMode(RELAY1, OUTPUT);
  pinMode(RELAY2, OUTPUT);
  pumpsOff();
  Serial.begin(115200);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  digitalWrite(TRIG_PIN, LOW);
  gateServo.setPeriodHertz(50);
  sortServo.setPeriodHertz(50);
  gateServo.attach(GATE_SERVO_PIN, 500, 2400);
  sortServo.attach(SORT_SERVO_PIN, 500, 2400);
  servoReady = gateServo.attached() && sortServo.attached();
  resetSystem();
  sendLine("EcoRefill ESP32 Starting");
}

void loop() {
  serviceInput();
  serviceOperation();
  serviceOutput();
  delay(1); // Yield to ESP32 system tasks; no multi-second operation delays.
}
