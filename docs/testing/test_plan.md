# Special Exams Test Plan

This document should serve as a catalogue of key features included in the proctoring/special-exams system. It may be used in part, or in full, whenever manual testing is required.

## Resources

#### Test Courses in Stage
- [course-v1:Proctoring2+Proctoring2+Proctoring2](https://learning.stage.edx.org/course/course-v1:Proctoring2+Proctoring2+Proctoring2/home) (RPNow)

#### Django Admin Models
- Exam Attempt: https://courses-internal.stage.edx.org/admin/edx_proctoring/proctoredexamstudentattempt/
- Exam Review: https://courses-internal.stage.edx.org/admin/edx_proctoring/proctoredexamsoftwaresecurereview/

#### Useful Queries
- Certificate Status: `select status from certificates_generatedcertificate where name = <username> and course_id = <course_key>;`

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
- [ ] The exam timer is shown and functions properly. [Exam Timer](#exam-timer)
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
- [ ] The timer should return with the correct value (meaning it continues to count down on the backend) when you:
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

#### If the exam timer reaches zero the exam is automatically submitted
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

## Proctored Exam

### Test Cases

#### <a name="proctored-exam"></a> A paid track learner is able to start, complete, and submit a proctored exam
- [ ] Log in as a verified learner and navigate to the proctored exam section
- [ ] You should see an interstitial with the following information:
    - [ ] Statement that this is a proctored exam
    - [ ] A button or link to continue
- [ ] Click the link to continue
- [ ] You should see an interstitial prompting you to set up the proctoring software
- [ ] Click start system check or copy/paste the exam code to follow steps according to the proctoring software
- [ ] After set up you should be returned to edx courseware and the start exam button should be enabled
- [ ] You should see a final interstitial stating the rules of the proctored exam and the time allotted to complete it
    - [ ] There should be a functioning link to the support docs four proctored exam rules
- [ ] Click start my exam
- [ ] You should see the first unit in the exam
- [ ] The exam timer is shown and functions properly. [Exam Timer](#exam-timer)
- [ ] Click end my exam on the banner
- [ ] Click submit on the confirmation page
- [ ] You should see an interstitial confirming the exam has been submitted and is waiting on review
- [ ] You should receive an email stating your exam has been submitted for review
- [ ] This test has been completed with a Proctortrack exam
- [ ] This test has been completed with a RPNow exam

#### <a name="error"></a> Learners are removed from the exam if connectivity to the proctoring software is not maintained
- [ ] Log in as a verified learner, navigate to the exam section, follow all instructions, and start the exam
- [ ] Interrupt session by either closing the proctoring in software or disconnecting your internet
- [ ] Wait up to 1-2 minutes, but no more than five.
- [ ] You should see an interstitial stating that an error has occurred
- [ ] you can no longer view the exam content

#### <a name="learner-resume"></a>Learners are able to resume an exam upon approval from the course team
- [ ] Follow steps to start and be removed from an exam due to a connection error, make note of the time remaining. [Exam With Error State](#error)
- [ ] In another browser, use the instructor dashboard to resume the learner exam attempt. [Resume Exam](#resume-exam)
- [ ] Return as the learner and navigate to the exam section
- [ ] You should see an interstitial stating that the exam is ready to resume
    - [ ] The time remaining should match that noted just before being removed from the exam due to an error
- [ ] You should be able to successfully complete and submit to the exam
- [ ] You should receive an email stating your exam has been submitted for review


#### Additional features
- [ ] Missing and pending prerequisites
- [ ] Missing and pending verification
- [ ] Proctored exam opt-out and its impact on other proctored exams in the course
- [ ] Incorrect browser during RPNow exam

## Onboarding Exam

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

#### A learner can retry an onboarding exam in the error or rejected status
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

#### Additional Features
- [ ] Onboarding status panel for missing and completed onboarding profiles
- [ ] Onboarding status panel for expired or exams that have not yet been released

## Certificates and Grades

#### A rejected exam review should invalidate certificate and set grade to 0
- [ ] Login as a verified learner and complete enough content so that completing an exam will earn you a passing grade
- [ ] Follow steps to start, complete, and submit a proctored exam. [Proctor Exam](#proctor-exam)
    - [ ] make sure to receive a grade that will meet the threshold for passing the course
- [ ] Get the `external_id` of the attempt from LINK
- [ ] As an admin user use the external id to send a POST request to the exam review endpoint with a status of `suspicious`
    - [ ] An alternative is to wait for this review to come back organically (may take 24hrs)
- [ ] Update the review from `suspicious` to `rules violation` in [Django Admin](#django-admin-models)
- [ ] Validate the exam grade has been overridden to zero using gradebook
- [ ] Query read replica to validate the certificate has been marked `unavailable` [Useful Queries](#useful-queries)

#### If a learner has multiple sessions for an exam, a falling review of either recording should invalidate the certificate and set the grade to 0
- [ ] Login as a verified learner and complete enough content so that completing an exam will earn you a passing grade
- [ ] Follow steps to put your exam attempt in the `error` state. [Exam With Error State](#error)
- [ ] In another browser, use the instructor dashboard to allow this learner to resume
- [ ] Returned to the learner's browser, refresh the page, start, complete, and submit the exam.
    - [ ] make sure to receive a grade that will meet the threshold for passing the course
- [ ] Get the `external_id` of both the resumed and submitted attempts from [Django Admin](#django-admin-models)
- [ ] As an admin user use the external id of the resumed attempt to send a POST request to the exam review endpoint with a status of `passed`
    - [ ] An alternative is to wait for this review to come back organically (may take 24hrs)
- [ ] As an admin user use the external id of the submitted attempt to send a POST request to the exam review endpoint with a status of `suspicious`
- [ ] Update the review from `suspicious` to `rules violation` in [Django Admin](#django-admin-models)
- [ ] Validate the exam grade has been overridden to zero using gradebook (tab in instructor dashboard)
- [ ] Query read replica to validate the certificate has been marked `unavailable` [Useful Queries](#useful-queries)

## Instructor Dashboard

### Test Cases

#### Individual exam attempts are shown and may be removed by the instructor
- [ ] As a learner, enter a timed exam section and complete at least one unit in the exam
- [ ] In another browser, navigate to the instructor dashboard and expand the "Student Special Exam Attempt" section
- [ ] There should be an attempt by the learner in step #1 with the correct status, exam name, and date.
- [ ] The "Actions" column should have one link to "Reset"
- [ ] Reset the exam and click yes on the confirmation alert
- [ ] Return to the exam as the learner
- [ ] You should see the initial interstitial indicating that this is a timed exam
- [ ] Enter the exam, any previously completed units should be reset

#### <a name="resume-exam"></a> Exam attempts in the error state may be resumed
- [ ] Follow steps to start and be removed from an exam due to a connection error, make note of the time remaining. [Exam With Error State](#error)
- [ ] In another browser, navigate to the instructor dashboard and expand the "Student Special Exam Attempt" section
- [ ] Find the attempt for learner in step #1. There should be a gear icon in the "Actions" column that unveils two options: "reset" and "resume"
- [ ] Click resume and accept the confirmation message
- [ ] Return to the learner's browser. [Learners should be able to resume and complete the exam](#learner-resume)

#### Multiple sessions for the same exam (due to a resume) appear as a group and can be removed in bulk
- [ ] Follow the steps to put an exam in the error state and submit a resumed attempt as the learner [Resume Exam](#resume-exam)
- [ ] Navigate to the instructor dashboard and expand the "Students Special Exam Attempt" section
- [ ] Find the attempt for the learner and step #1.
- [ ] This row should expand to display two distinct attempts with the appropriate dates and status
- [ ] Click the reset button. Both attempts should be removed.
- [ ] Return to the learner's browser and return to the exam section.
- [ ] The learner should be able to start and complete a new attempt.

#### Onboarding status view includes all paid-track learners and is filterable
- [ ] And sure you have a at least one learner in your course that:
    - [ ] Has not started onboarding
    - [ ] Has completed onboarding
- [ ] Download the course roster using the "Data Download" tab on the instructor dashboard
    - [ ] A CSV learners can be downloaded by clicking the "Donald profile information as a CSV" button
- [ ] Filter the audit learners out of the report
- [ ] View the special exams tab and open the "Student Onboarding Status" dropdown
- [ ] Ensure all learners in the CSV have a row in the drop down
- [ ] Filtering by "Not Started" it includes the learner(s) who has not started onboarding
- [ ] Filtering by multiple statuses functions as expected

#### Additional Features
- [ ] Allowances
