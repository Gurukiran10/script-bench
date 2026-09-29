# What makes a script "good"

A short-form script is judged second by second, by a viewer who's one thumb movement away from leaving. So "good" isn't about how it reads. It's about whether it survives being *watched*.

**The hook makes a promise specific enough to be worth three more seconds.** "Saving money is important" promises nothing. "I haven't looked at my savings account in two years" makes the viewer want to know what's in it. Specific beats clever: a number, a moment, or a mistake the viewer recognises in themselves. No greeting, no warm-up. The first word is already the content.

**The body keeps that promise, early.** The most common failure is a body that wanders off from the hook, or saves the payoff until second 40. A good body pays off the hook in the first beat and then adds one new thing per beat: a step, a proof, an example, a turn. It ends on a line the viewer would repeat to a friend.

**It's written for the ear.** Short sentences, contractions, one idea at a time. Nothing the creator will stumble over and nothing that only works as text. It fits the runtime the creator asked for, because a 60-second script squeezed into 30 seconds gets rushed or cut badly on set.

**The close asks for one thing, and that thing follows from the video.** "Comment the first bill you'd automate" works because the viewer just thought about it. "Like, comment and subscribe" is three asks nobody hears.

**It's true.** Specific details make a script, and they're exactly what a language model invents. A good script doesn't put a made-up statistic in a real person's mouth.

## How the generator gets there

Each of those qualities is either a writing problem or a checking problem, and I split them that way.

The **model** handles the writing: voice, rhythm and the specific details. It's asked to commit to one *angle* (the payoff) before writing anything, then to write three hooks in deliberately different styles that all promise that angle, then the body and CTA around it. Committing to the angle first is what keeps the hook and the body in sync.

**Code** handles everything that has to be reliable. The runtime becomes a spoken-word budget. A ranker picks the strongest hook and throws out ones that open with a greeting or run too long. A critic checks timing, a single-ask CTA, stock phrases, stage directions and sentences too long to say in one breath, then sends each problem back to the model as a specific fix. Every version is scored and the best one wins, so revising can't make a script worse. Invented numbers aren't banned. They're listed under "check before filming".

The limit I'd point to myself: my rules can tell when a script is *bad*, but not when it's *good*. The rules-only fallback passes the critic on some topics while reading like filler. Taste still comes from the model. The system's job is to stop it from failing in the predictable ways.
