# Special Exams Test Plan

This document should serve as a catalogue of key features included in the proctoring/special-exams system. It may be used in part, or in full, whenever manual testing is required.

## Resources

#### Test Courses in Stage
- course-v1:edX+cheating101+2018T3
- course-v1:edX+StageProctortrack+2019

#### Django Admin Models
- Exam Attempt: https://courses-internal.stage.edx.org/admin/edx_proctoring/proctoredexamstudentattempt/
- Exam Review: https://courses-internal.stage.edx.org/admin/edx_proctoring/proctoredexamsoftwaresecurereview/

#### Useful Queries
- Certificate Status: `select status from certificates_generatedcertificate where name = <name> and course_id = <course_key>;`

## Smoke Test

Efficient testing path that covers core functions.

--TODO--


# Features

## Timed Exam

### Test Cases

#### A paid track learner is able to start, complete, and submit a timed exam
- [ ] Log in as a verified learner and navigate to the exam section
- [ ] You should see an interstitial with the following information:
    - [ ] Statement that this is a timed exam
    - [ ] The number of minutes allowed to complete the exam. This should match the `time allotted` value in studio.
    - [ ] A button or link to start the exam
- [ ] Click the link to start the exam
- [ ] You should see the first unit in the exam
- [ ] The exam timer is shown and functions properly (LINK)
- [ ] Click end my exam using the timer banner
- [ ] You should see an interstitial confirming if you want to submit
- [ ] Submit the exam
- [ ] You should see an interstitial confirming the exam has been submitted
- [ ] If you navigate away and return to this section you should still see the submitted interstitial

#### A paid track learner is not able to enter an expired exam (Instuctor paced courses only)

- [ ] In studio, set the due date for the exam in the past
- [ ] Log in as a verified learner and navigate to the timed exam section
- [ ] An interstitial is shown stating that the due date for this exam has passed

## Exam Timer

#### The exam timer functions during a timed special exam
- [ ] Log in as a verified learner and begin a timed or proctored exam
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

#### A learner is given limted time if starting a exam that is nearly due
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

#### A paid track learner is able to start, complete, and submit a proctored exam
- [ ] Log in as a verified learner and navigate to the proctored exam section
- [ ] You should see an interstitial with the following information:
    - [ ] Statement that this is a proctored exam
    - [ ] A button or link to continue
- [ ] Click the link to continue
- [ ] You should see an interstitial prompting you to set up the proctoring software
- [ ] Click start system check and follow set up steps according to the proctoring software
- [ ] After set up you should be returned to edx courseware and the start exam button should be enabled
- [ ] You should see a final interstitial stating the rules of the proctored exam and the time allotted to complete it
    - [ ] valid link??
- [ ] Click start my exam
- [ ] You should see the first unit in the exam
- [ ] The exam timer is shown and functions properly (LINK)
- [ ] Click end my exam on the banner
- [ ] Click submit on the confirmation page
- [ ] You should see an interstitial confirming the exam has been submitted and is waiting on review
- [ ] You should receive an email stating your exam has been submitted for review

- [ ] This test has been completed with a Proctortrack exam
- [ ] This test has been completed with a RPNow exam

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
- Incorrect browser during RPNow exam

## Onboarding Exam

### Test Setup
Manually update attempt status: https://courses-internal.stage.edx.org/admin/edx_proctoring/proctoredexamstudentattempt/
https://courses-internal.stage.edx.org/admin/edx_proctoring/proctoredexamsoftwaresecurereview/

### Test Cases

#### And approved onboarding profile is required to begin a proctored exam
- [ ] Ensure you have a learner account without a verified onboarding profile
    - [ ] If not, use the instructor dashboard to remove any prior onboarding attempts
- [ ] Log in as a verified learner and navigate to the proctored exam section
- [ ] Click the link on the first interstitial to start your exam
- [ ] You should be blocked from the exam with a message stating you must complete onboarding
- [ ] This page should include a link to the onboarding exam
- [ ] Click "Navigate to Onboarding Exam"
- [ ] You should be sent to the onboarding exam for this course

- [ ] This behavior should be the same if the learner has a rejected onboarding profile
- [ ] The "Navigate to Onboarding Exam" link should be omitted if the learner's onboarding profile is pending review

#### A learner is able to start, complete, and submit an onboarding exam
- [ ] Log in as a verified learner and navigate to the proctored exam section
- [ ] You should see an interstitial with the following information:
    - [ ] Statement that this is a onboarding exam
    - [ ] A button or link to continue
- [ ] Click the link to continue
- [ ] You should see an interstitial prompting you to set up the proctoring software
- [ ] Click start system check and follow set up steps according to the proctoring software
- [ ] During setup you should be prompted for a face scan and id photo
- [ ] After set up you should be returned to edx courseware and the start exam button should be enabled
- [ ] You should see a final interstitial stating the rules of the proctored exam and the time allotted to complete it
- [ ] After being redirected to edx course war you should be able to start and submit your exam
- [ ] You should see an interstitial confirming the exam has been submitted and is waiting on review
- [ ] You should receive an email stating your exam has been submitted for review

#### A learner can retry an onboarding exam in the error and rejected status
- [ ] Login is a verified learner and navigate to the proctored exam section. This will create an exam attempt.
- [ ] As an admin, in another browser, manually update the `created` attempt status to `error` LINK
- [ ] Return to the learner's examine refresh the page
- [ ] You should be presented with an error message and a button to "Retry my exam"
- [ ] Clicking retry my exam should direct the learner back to the start system check page
- [ ] You should be able to follow the steps to start, complete, and submit the onboarding exam.
- [ ] As an admin, in another browser, manually update the `created` attempt status to `rejected` LINK
- [ ] Return to the learner's examine refresh the page
- [ ] You should be presented with a rejected message and a button to "Retry my exam"
- [ ] Clicking retry my exam should direct the learner back to the start system check page
- [ ] You should be able to follow the steps to start, complete, and submit the onboarding exam.


## Certificates and Grades

#### A rejected exam review should invalidate certificate and set grade to 0
- [ ] Login as a verified learner and follow steps to start, complete, and submit a proctored exam
    - [ ] Make sure to receive a grade greater than 0
- [ ] Get the `external_id` of the attempt from LINK
- [ ] As an admin user use the external id to send a POST request to the exam review endpoint with a status of `suspicious`
- [ ] Update the review from `suspicious` to `rules violation` LINK
- [ ] Validate the exam grade has been overridden to zero using gradebook LINK
- [ ] use the following query against reed replica to validate the certificate has been marked `unavailable`
    - [ ] `select * from proctoring_proctoredexamstudentattempt where user_id = <id> and proctored_exam_id = <id>;`

#### If a learner has multiple sessions for an exam, a falling review of either recording should invalidate thie certificate and set the grade to 0
- [ ] Login as a verified learner and follow steps to put your exam attempt in the `error` state LINK
- [ ] In another browser, use the instructor dashboard to allow this learner to resume
- [ ] Returned to the learner's browser, refresh the page, start, complete, and submit the exam.
    - [ ] make sure to receive a grade that will meet the threshold for passing the course
- [ ] Get the `external_id` of both the resumed and submitted attempts from LINK
- [ ] As an admin user use the external id of the resumed attempt to send a POST request to the exam review endpoint with a status of `passed`
- [ ] As an admin user use the external id of the submitted attempt to send a POST request to the exam review endpoint with a status of `suspicious` 
- [ ] Update the review from `suspicious` to `rules violation` LINK
- [ ] Validate the exam grade has been overridden to zero using gradebook LINK
- [ ] use the following query against reed replica to validate the certificate has been marked `unavailable`

#### If a learner has multiple sessions for an exam, a certificate is not released until all reviews are verified
- [ ] TODO -- I was under the impression this was the case but my testing of the behavior seems to indicate we do release a certificate so long as neither review is rejected.

## Instructor Dashboard

### Test Cases

#### Individual exam attempts may be removed

#### Exam attempts in the error state may be resumed

#### Multiple sessions for the same exam (due to a resume) appear as a group

#### Multiple sessions for the same exam are deleted in bulk

#### Onboarding status view includes all paid-track learners

#### Onboarding Status View is filterable

#### Allowances...

# single path smoke test???
# other paid tracks???