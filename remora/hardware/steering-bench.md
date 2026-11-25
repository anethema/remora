# Winter steering bench for the 30 lbf trolling motor

The first measurement for Remora is how much torque it takes to turn the owner's motor, and how quickly a linkage can position its shaft. Keep the propulsion battery disconnected throughout the bench work. A separate PWM servo tester and regulated supply can exercise the steering independently. All hardware selections below are provisional.

## Parts in build order

| Stage | Parts | What determines the choice |
| --- | --- | --- |
| Measure | Existing motor and mount, secured scrap transom, spring or fish scale, ruler, shaft pointer and paper protractor | Use the normal shaft depth and steering tension. Record the make, model, mount geometry and available clearance. |
| Mock up | Fixed bracket, servo horn, adjustable pushrod, two articulated rod ends, removable clevis pin and short tiller arm | Mount the bracket to a part that tilts with the motor but stays fixed while steering. Attach the tiller arm to a suitable rigid rotating point. A printed bracket is useful for checking fit. |
| Exercise steering | Metal-geared positional servo, PWM tester and a regulated supply sized for the chosen servo's voltage and transient current | Select after measuring torque, angular travel and required linkage leverage. If the rotary package cannot meet all three, compare a geared actuator with position feedback. |
| Later electronics | ArduPilot Rover-compatible controller, external GNSS/compass, power/current monitor, independent propulsion disconnect and appropriate fuse | Identify the actual motor, voltage, maximum current and speed-control design before selecting an electrical throttle driver. Steering uses one mechanical actuator. |

## Bench procedure

1. Secure the original motor mount on a scrap transom. Record the tension-adjustment setting. Mark shaft centre and angles to each side. Photograph the head and mount from above and the side with a ruler in frame.
2. Pull the scale perpendicular to a rigid arm at a known distance from the steering axis. Record the highest force to start moving, and the force during slow movement in each direction. Repeat at centre and near both ends of the intended sweep. Steering torque in N·m equals force in newtons times radius in metres. For a scale reading in lbf, multiply the reading by 4.448 and by the radius in metres. A 5 lbf reading at 100 mm gives 2.22 N·m at the motor pivot.
3. Mock up the linkage by hand. Check the available sweep, cable slack and tilt clearance. Keep the rod clear of dead centre throughout travel. Check that pulling the clevis pin restores hand steering. A longer tiller arm gives more torque for the same rod force and needs more rod travel for the same shaft angle.
4. Choose a positional actuator with adequate working torque through the entire linkage and sufficient angular travel. For scale, Hitec lists 1.96 N·m stall torque and 4.2 A stall current at 6 V for the D956WP. Stall is a limiting condition. Sustained steering needs operating margin, and a dry pull only measures the bench load. [Hitec datasheet](https://www.hiteccs.com/public/uploads/data_sheet/D956WP-DataSheet-1642815611.pdf)
5. With only the steering powered, command port, centre and starboard using the tester. Record actual shaft angles, sweep times in both directions, centre error after approaching from each side, peak supply current and any binding over repeated cycles. Keep the physical rig independent of the simulation dashboard.

## Measurement sheet

| Measurement | Owner's result |
| --- | --- |
| Motor nameplate, mount photos and tension setting | Pending |
| Scale lever arm and units | Pending |
| Peak starting and slow moving force, port / starboard | Pending |
| Servo horn and tiller arm radii, shaft travel achieved | Pending |
| Loaded sweep time, port to starboard / return | Pending |
| Centre error from each direction, supply voltage and peak current | Pending |

The current external plant assumes ±35° and a shaft rate limit of 1 rad/s, giving an ideal 1.22 s for the full 70° sweep. Use the measured angles and time to calibrate the simulated actuator. Water trials with an operator aboard, independent stop and recovery, and no divers nearby are a later step for measuring steering loads under thrust. The 30 lbf setup can establish geometry and measurement technique for a larger motor. Repeat the load measurements on the final motor and mount.

Rover already supports independent steering and throttle outputs. The steering rig can be developed before buying a flight controller or deciding how to control the propulsion motor electrically. [ArduPilot Rover motor and servo connections](https://ardupilot.org/rover/docs/rover-motor-and-servo-connections.html)
