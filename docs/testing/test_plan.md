# Special Exams Test Plan

This document should serve as a catalogue of features included in the proctoring/special-exams system. It can be used in part, or in full, whenever manual testing is required.

## Available Test Courses
- course-v1:edX+cheating101+2018T3
- course-v1:edX+StageProctortrack+2019


# Features

## Timed Exam

### Required Setup
- [ ] An instructor-paced test course with at least one timed exam

### Test Cases

#### A verified learner is able to start, complete, and submit a timed exam
- [ ] Log in as a verified learner and navigate to the exam section
- [ ] You should see an interstitial with the following information:
    - [ ] Statement that this is a timed exam
    - [ ] The number of minutes allowed to complete the exam. This should match the `time allotted` value in studio.
    - [ ] A button or link to start the exam
- [ ] Click the link to start the exam
- [ ] You should see the first unit in the exam
- [ ] Click and my exam using the timer banner
- [ ] You should see an interstitial confirming if you want to submit
- [ ] Submit the exam
- [ ] You should see an interstitial confirming the exam has been submitted
- [ ] If you navigate away and return to this section you should still see the submitted interstitial

#### A learner is not able to enter an expired exam (Instuctor paced courses only)

- [ ] In studio, set the due date for the exam in the past
- [ ] Log in as a verified learner and navigate to the timed exam section
- [ ] An interstitial is shown stating that the due date for this exam has passed

#### Additional Features
- review exam answers after due

## Exam Timer

#### The exam timer functions during a timed special exam
- [ ] Log in as a verified learner and and beginning timed or proctored exam
- [ ] When viewing exam content there should be a banner with the following information:
    - [ ] Notification you that you are in a timed exam
    - [ ] A button to end the exam
    - [ ] A timer counting down from the correct `time allotted` for this exam
- [ ] The timer should return with the correct value when you:
    - [ ] Refresh the page
    - [ ] Navigate to other course content, then return to the exam
- [ ] Click end my exam on the banner
- [ ] You should see an interstitial confirming if you want to submit
    - [ ] The timer should continue to count down
- [ ] Click I want to continue working
- [ ] You should be returned to the exam content
- [ ] Click end my exam on the banner
- [ ] Click submit on the confirmation page
- [ ] You should see an interstitial confirming the exam has been submitted

#### If the exam timer reaches zero the exam is automatically submitted if timeouts are allowed
- [ ] (optional) In studio, set `time allotted` on the timed exam to 2-3 minutes to ease testing
- [ ] Log in as a verified learner and begin the timed exam
- [ ] Observe the timer as it approaches zero
- [ ] The timer should visually indicate low time remaining
- [ ] The timer should pause at 00:00 for approximately 5 seconds
- [ ] An interstitial is shown notifying the learner their exam time has expired and answers have been automatically submitted.
- [ ] If you modified `time allotted` please reset it to the initial value

#### A learner is given limted time if stating a exam that is nearly due
- [ ] In studio, verify `time allotted` for the exam is greater than 5 minutes
- [ ] In studio, set the due date for the exam to 5 minutes from now
- [ ] Log in as a verified learner and navigate to the timed exam section
- [ ] You should see an interstitial that you have 5 minutes to complete the exam
- [ ] Begin the exam, the timer should reflect the reduced time limit

#### If the exam timer reaches zero and timeout is not allowed...
- [ ] ????? there is no view template for this case, wut ?????

## Proctored Exam

- [ ] A test course with proctoring enabled, and Proctortrack set as the backend provider
    - [ ] 
- [ ] A test course with proctoring enabled, RPnow said as the backend provider

### Test Cases

#### A verified learner is able to start, complete, and submit a proctored exam
- [ ] Log in as a verified learner and navigate to the exam section
- [ ] You should see an interstitial with the following information:
    - [ ] Statement that this is a proctored exam
    - [ ] A button or link to continue
- [ ] Click the link to continue
- [ ] You should see an interstitial prompting you to set up the proctoring software
- [ ] Click start system check and follow set up steps according to the proctoring software
- [ ] After set up you should be returned to edx courseware and the start exam button should be enabled
- [ ] You should see a final interstitial stating the rules of the proctored exam and the time allotted to complete it
- [ ] Click start my exam
- [ ] You should see the first unit in the exam
- [ ] There should be a banner with the following information:
    - [ ] Notification you that you are in a timed exam
    - [ ] A button to end the exam
    - [ ] A timer counting down from the correct `time allotted` for this exam
- [ ] The timer should return with the correct value when you:
    - [ ] Refresh the page
    - [ ] Navigate to other course content, then return to the exam
- [ ] Click end my exam on the banner
- [ ] You should see an interstitial confirming if you want to submit
    - [ ] The timer should continue to count down
- [ ] Click I want to continue working
- [ ] You should be returned to the exam content
- [ ] Click end my exam on the banner
- [ ] Click submit on the confirmation page
- [ ] You should see an interstitial confirming the exam has been submitted and is waiting on review
- [ ] You should receive an email stating your exam has been submitted for review

- [ ] Test has been completed with a Proctortrack exam
- [ ] Test has been completed with a RPNow exam

#### Learners are removed from the exam if connectivity to the proctoring software is not maintained
- [ ] Log in as a verified learner, navigate to the exam section, follow all instructions, and start the exam
- [ ] Interrupt session by either closing the proctoring in software or disconnecting your internet
- [ ] Wait up to two minutes
- [ ] You should see an interstitial stating that an error has occurred
- [ ] you can no longer view the exam content

#### Learners are able to resume an exam upon approval from the course team
- [ ] Follow steps to be removed from an exam due to a connection error, make note of the time remaining
- [ ] TODO instructor steps to reset
- [ ] Log in as a verified learner and navigate to the exam section
- [ ] You should see an interstitial stating that the exam is ready to resume
    - [ ] The time remaining should match that noted just before being removed from the exam due to an error
- [ ] You should be able to successfully complete and submit to the exam
- [ ] You should receive an email stating your exam has been submitted for review

#### Additional features
- Missing prerequisites
- Proctored exam opt-out
- RPNow wrong browser

## Onboarding Exam

## Certificates and Grades
- certificate not released until all attempts are verified

## Instructor Dashboard
- exam reset
- exam resume
- onboarding status view
- exam attempt view
- allowances

# single path smoke test???