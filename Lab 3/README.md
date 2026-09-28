# Chatterboxes

Arnav Whig 

Shifen Hong


# Part 1

## Setup

Done

## A. Text to Speech

Done

\*\***Write your own shell file to use your favorite of these TTS engines to have your Pi greet you by name.**\*\*
(This shell file should be saved to your own repo for this lab.)

\*\***Then answer: Is the same greeting, in these different voices, the same greeting? Describe one concrete way the voice changed what the utterance seemed to mean or who seemed to be speaking.**\*\*

No the greeting sounds very different. The classic engines have very robotic voices which sound like they are pronouncing a word at a time in different breaths with no continuity. The Neural TTS with Piper model is a lot better making it sound a lot less robotic and a lot more natural. 

## B. Speech to Text

Done

\*\***Record a few seconds of your own speech (`arecord -d 5 -f cd -c 1 -r 16000 test.wav`) and transcribe it with at least two model sizes. Report the real-time factor for each. At what point does the accuracy improvement stop being worth the delay, for a system that has to answer you?**\*\*

## Speech-to-Text Model Comparison

I recorded a 5-second audio clip saying, "Hello, check one, two," and transcribed it using three different Whisper model sizes.

| Model      | Transcript               | Transcription Time | Real-Time Factor |
| ---------- | ------------------------ | -----------------: | ---------------: |
| `tiny.en`  | "Hello check one do."    |             0.89 s |            0.18x |
| `base.en`  | "Hello, check 1-2."      |             1.84 s |            0.37x |
| `small.en` | "Hello, check one, two." |             5.22 s |            1.04x |

The `tiny.en` model was the fastest, with a real-time factor of `0.18x`, but it incorrectly transcribed "two" as "do." The `base.en` model was more accurate and still relatively fast, with a real-time factor of `0.37x`. It transcribed the phrase as "Hello, check 1-2," which preserved the meaning correctly.

The `small.en` model produced the most accurate transcription, exactly recognizing "Hello, check one, two." However, its real-time factor was `1.04x`, meaning it took slightly longer to transcribe the audio than the duration of the audio itself.

For an interactive system that needs to respond quickly, I think `base.en` gives the best balance between accuracy and speed for this example. The accuracy improvement from `base.en` to `small.en` was relatively small, while the transcription time increased from 1.84 seconds to 5.22 seconds. For a conversational system, that extra delay could make the interaction feel noticeably slower.

\*\***Write your own script that verbally asks for a numerical input (a phone number, zipcode, number of pets) and records the answer the respondent provides.**\*\* Numbers are a good stress test — transcription systems make characteristic errors on digit strings, and you will want to know what they are before you design around them.

Done

## C. Turn-taking: knowing when someone has stopped talking

Done

\*\***Try both extremes, and something in between. Describe what each one feels like to talk to. Note specifically: at 0.2s, what kinds of normal speech get cut off? At 1.5s, what does the delay make the system seem like?**\*\*

After trying both I realized this variable is probably very important because with cutoff at only 0.2 I was id sentence and about to start saying something else that wasn't picked up while the other 1.5s cutoff was enough to get all my speech it was recording for much longer then I hoped. Depending on context there is probably a favorable cutoff.

There is no correct value. A system that takes drink orders and a system that listens to someone think out loud want very different thresholds, and the right one depends on what your users are doing with their pauses.

### The complete loop

`echo_bot.py` puts the pieces together: it listens, endpoints, transcribes, and speaks a reply through Piper. The dialogue policy is deliberately trivial — it repeats what you said — so that everything you notice is a property of the timing rather than the content.

```
(.venv) $ python echo_bot.py
```

## D. Storyboard

Storyboard and/or use a Verplank diagram to design a speech-enabled device. (Stuck? Make a device that talks for dogs. If that is too stupid, find an application that is better than that.)

\*\***Post your storyboard and diagram here.**\*\*
<img width="3053" height="2292" alt="image" src="https://github.com/user-attachments/assets/7eec1117-758b-4f6f-8fce-8ad80d10e27e" />

<img width="2818" height="2823" alt="image" src="https://github.com/user-attachments/assets/6dd6f48c-dabc-4b7b-b9a8-40915bcf4bb7" />

Write out what you imagine the dialogue to be. Use cards, post-its, or whatever method helps you develop alternatives or group responses.

<img width="4536" height="8064" alt="IMG_6842" src="https://github.com/user-attachments/assets/5e53de0f-cbac-4230-af69-f7b9f63acef8" />
On occasion of silence, the VAD should wait up to 5 seconds, then the box will speak on its own, asking "is anyone there?".

## E. Acting out the dialogue

Find a partner, and *without sharing the script with your partner* try out the dialogue you've designed, where you (as the device designer) act as the device you are designing. Please record this interaction (for example, using Zoom's record feature).

[video](https://youtu.be/IDa1cwQhbnY)

\*\***Describe if the dialogue seemed different than what you imagined when it was acted out, and how.**\*\*
The dialogue diverge from script when the user ask me to explain which planet I am from, this is something that I did not have a response prepared for, so I have to improvise and guide him to say the things that is in the designed flow.



---

# Lab 3 Part 2

For Part 2, you will redesign the interaction with the speech-enabled device using the data collected, as well as feedback from part 1.

## Prep for Part 2

1. What are concrete things that could use improvement in the design of your device? For example: wording, timing, anticipation of misunderstandings.
2. What are other modes of interaction *beyond speech* that you might also use to clarify how to interact? In particular: how does someone know when the device is listening, and when it is thinking? You have a screen and an LED.
3. Make a new storyboard, diagram and/or script based on these reflections.
4. (optional) Integrate [input devices](inputs.md) in the system

## Prototype your system

The system should:
* use the Raspberry Pi
* use one or more sensors
* require participants to speak to it

*Document how the system works.*

*Include videos or screencaptures of both the system and the controller.*

## Test the system

Try to get at least two people to interact with your system. (Ideally, you would inform them that there is a wizard *after* the interaction, but we recognize that can be hard.)

Answer the following:

### What worked well about the system and what didn't?
\*\**your answer here*\*\*

### What worked well about the controller and what didn't?
\*\**your answer here*\*\*

### What lessons can you take away from the WoZ interactions for designing a more autonomous version of the system?
\*\**your answer here*\*\*

### How could you use your system to create a dataset of interaction? What other sensing modalities would make sense to capture?
\*\**your answer here*\*\*

<details>
  <summary><strong>Submission Cleanup Reminder (Click to Expand)</strong></summary>

  **Before submitting your README.md:**
  - This readme.md file has a lot of extra text for guidance.
  - Remove all instructional text and example prompts from this file.
  - You may either delete these sections or use the toggle/hide feature in VS Code to collapse them for a cleaner look.
  - Your final submission should be neat, focused on your own work, and easy to read for grading.
</details>
