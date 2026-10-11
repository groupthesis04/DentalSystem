<script setup>
import { Heart, MessageCircle, ShieldCheck, Sparkles, Target, UsersRound } from "lucide-vue-next";

const values = [
  {
    title: "Understanding & Choice",
    description:
      "Patients deserve to understand their own oral health. We communicate clearly, present appropriate options, answer questions honestly, and respect every patient's right to decide.",
    icon: MessageCircle,
  },
  {
    title: "Care With Purpose",
    description:
      "Every recommendation we make should have a reason. We aim for dentistry that is thoughtful, appropriate, preventive, and focused on long-term oral health—not simply treating problems as they appear.",
    icon: Target,
  },
  {
    title: "Excellence With Humility",
    description:
      "We continuously learn, improve, and refine the way we practice. We value knowledge and skill while remaining open to better ideas, better techniques, and better ways of caring for people.",
    icon: Sparkles,
  },
  {
    title: "Trust Is Earned",
    description:
      "Trust isn't created by promises. It is built through consistency, honesty, transparency, respect, and doing what we say we will do.",
    icon: ShieldCheck,
  },
  {
    title: "Comfort Matters",
    description:
      "A patient's emotional experience matters just as much as the treatment itself. We strive to create an environment where people feel welcomed, respected, and at ease.",
    icon: Heart,
  },
  {
    title: "One Team, One Purpose",
    description:
      "Every member of Borja Dental Clinic contributes to the patient's experience. We support each other, communicate with one another, and work together toward one purpose: to make every patient feel that they are in good hands.",
    icon: UsersRound,
  },
];

const teamExpectations = [
  "Treat every patient with genuine kindness and respect.",
  "Listen before making assumptions.",
  "Communicate clearly and honestly.",
  "Protect the trust patients place in us.",
  "Maintain high standards of professionalism and clinical care.",
  "Keep learning and improving.",
  "Support one another rather than compete with one another.",
  "Take responsibility for the patient's overall experience.",
  "Create a clinic environment that feels welcoming—not intimidating.",
  "Remember that small acts of care can make a big difference.",
];

const careQuestions = [
  "Did our patient understand?",
  "Did our patient feel heard?",
  "Did our patient feel respected?",
  "Did our patient leave feeling cared for?",
];

const promises = [
  "We will listen to you.",
  "We will explain to you.",
  "We will respect your decisions.",
  "We will care about your comfort.",
  "We will be honest about your options.",
  "And we will walk with you toward better oral health.",
];
</script>

<template>
  <div class="about-story">
    <section id="core-values" class="about-story-values" aria-labelledby="about-values-heading">
      <div class="about-story-container">
        <header class="about-story-heading">
          <span class="section-kicker">What guides our care</span>
          <h2 id="about-values-heading">Our Core <span>Values</span></h2>
          <p>The principles that guide the care we provide and the way we treat every patient.</p>
        </header>
        <div class="about-story-value-grid">
          <article
            v-for="(value, index) in values"
            :key="value.title"
            class="about-story-value-card"
          >
            <span class="about-story-value-number">
              {{ String(index + 1).padStart(2, "0") }} <span>/ 06</span>
            </span>
            <span class="about-story-value-icon" aria-hidden="true">
              <component :is="value.icon" :size="26" :stroke-width="1.8" />
            </span>
            <h3>{{ value.title }}</h3>
            <p>{{ value.description }}</p>
          </article>
        </div>
      </div>
    </section>

    <section id="our-team" class="about-story-team" aria-labelledby="about-team-heading">
      <div class="about-story-container">
        <div class="about-story-team-intro">
          <div class="about-story-team-image">
            <img
              src="/assets/service_bg.png"
              alt="A dental professional caring for a patient at BORJA Dental Clinic"
              loading="lazy"
            />
          </div>
          <div class="about-story-team-copy">
            <span class="section-kicker">Our team</span>
            <h2 id="about-team-heading">
              We Don't Just Work Together. <span>We Care Together.</span>
            </h2>
            <p>At Borja Dental Clinic, teamwork is not simply about dividing responsibilities.</p>
            <p>
              It is about understanding that every interaction becomes part of the patient's
              experience.
            </p>
            <p>
              From the moment a patient walks through our door, every smile, every conversation,
              every explanation, and every detail of care matters.
            </p>
            <div class="about-story-belief">
              <span>Our shared belief</span>
              <strong>Every patient deserves to feel seen, heard, and cared for.</strong>
            </div>
          </div>
        </div>

        <div class="about-story-team-principles">
          <div class="about-story-principles-heading">
            <span class="section-kicker">What we stand for</span>
            <h3>How we care, <span>together</span></h3>
            <p>We expect our team members to:</p>
          </div>
          <ul class="about-story-checklist">
            <li v-for="expectation in teamExpectations" :key="expectation">
              <span aria-hidden="true">✓</span>
              {{ expectation }}
            </li>
          </ul>
        </div>

        <div class="about-story-reflection">
          <div>
            <span class="about-story-overline">Beyond every treatment</span>
            <h3>We don't measure our work only by the procedures we complete.</h3>
            <p>We also ask:</p>
          </div>
          <ul>
            <li v-for="question in careQuestions" :key="question">{{ question }}</li>
          </ul>
        </div>
        <p class="about-story-conclusion">
          Because at Borja Dental Clinic, the treatment may happen in the dental chair, but the
          experience begins long before the chair—and stays with the patient long after they leave.
        </p>
      </div>
    </section>

    <section id="our-promise" class="about-story-promise" aria-labelledby="about-promise-heading">
      <div class="about-story-container">
        <span class="about-story-promise-kicker">Our promise to every patient</span>
        <h2 id="about-promise-heading">
          “We will never make you feel like <span>just another patient.</span>”
        </h2>
        <div class="about-story-promise-grid">
          <p v-for="promise in promises" :key="promise">{{ promise }}</p>
        </div>
        <p class="about-story-promise-closing">
          Because your smile is not just part of your face.<br />It is part of who you are.
        </p>
        <div class="about-story-signature">
          <strong>BORJA Dental Clinic</strong>
          <span>“Your beautiful smile can be seen for miles and miles.”</span>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.about-story {
  color: var(--home-navy);
}

.about-story-container {
  width: min(1440px, calc(100% - 72px));
  margin-inline: auto;
}

.about-story-values,
.about-story-team,
.about-story-promise {
  scroll-margin-top: 100px;
}

.about-story-values {
  padding: 88px 0 96px;
}

.about-story-heading {
  max-width: 780px;
  margin: 0 auto 38px;
  text-align: center;
}

.about-story .section-kicker {
  display: inline-flex;
  width: fit-content;
  margin: 0 0 12px;
  border-radius: 999px;
  background: #f6e7c4;
  color: var(--home-gold-text);
  padding: 8px 16px;
  font-size: 0.78rem;
  font-weight: 900;
  text-transform: uppercase;
}

.about-story h2,
.about-story h3,
.about-story p {
  margin: 0;
}

.about-story h2,
.about-story-principles-heading h3 {
  color: var(--home-navy);
  font-family: var(--font-brand);
  font-weight: 700;
  letter-spacing: -0.04em;
  line-height: 1.08;
  text-wrap: balance;
}

.about-story h2 {
  font-size: clamp(2.5rem, 4.1vw, 4.25rem);
}

.about-story h2 span,
.about-story-principles-heading h3 span {
  color: var(--home-gold-text);
}

.about-story-heading > p {
  margin-top: 18px;
  color: #514c44;
  font-size: 1.08rem;
  line-height: 1.65;
}

.about-story-value-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 20px;
}

.about-story-value-card {
  position: relative;
  min-width: 0;
  border: 1px solid #ead9b8;
  border-radius: 16px;
  background: #fffefa;
  padding: 28px;
  box-shadow: 0 12px 32px rgba(23, 21, 17, 0.06);
}

.about-story-value-number {
  position: absolute;
  top: 30px;
  right: 28px;
  color: var(--home-gold-text);
  font-size: 0.82rem;
  font-weight: 900;
}

.about-story-value-number span {
  color: #8a8175;
  font-weight: 600;
}

.about-story-value-icon {
  display: grid;
  width: 54px;
  height: 54px;
  place-items: center;
  border-radius: 50%;
  background: #f6e7c4;
  color: var(--home-gold-text);
}

.about-story-value-card h3 {
  margin-top: 22px;
  color: var(--home-navy);
  font-family: var(--font-brand);
  font-size: 1.45rem;
  line-height: 1.2;
}

.about-story-value-card p {
  margin-top: 12px;
  color: #514c44;
  font-size: 0.98rem;
  line-height: 1.65;
}

.about-story-team {
  background: #f8f1e2;
  padding: 88px 0 82px;
}

.about-story-team-intro {
  display: grid;
  grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr);
  align-items: center;
  gap: clamp(34px, 5vw, 90px);
}

.about-story-team-image {
  height: 520px;
  overflow: hidden;
  border: 8px solid #fffefa;
  border-radius: 24px;
  background: #e8dfd0;
  box-shadow: 0 22px 50px rgba(72, 48, 17, 0.16);
}

.about-story-team-image img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center 36%;
}

.about-story-team-copy h2 {
  max-width: 780px;
  margin-bottom: 22px;
}

.about-story-team-copy > p {
  max-width: 700px;
  margin-top: 12px;
  color: #514c44;
  font-size: 1.04rem;
  line-height: 1.65;
}

.about-story-belief {
  display: grid;
  gap: 8px;
  max-width: 620px;
  margin-top: 28px;
  border-left: 4px solid #c49a46;
  padding: 12px 0 12px 22px;
}

.about-story-belief span,
.about-story-overline {
  color: var(--home-gold-text);
  font-size: 0.78rem;
  font-weight: 900;
  text-transform: uppercase;
}

.about-story-belief strong {
  color: var(--home-navy);
  font-family: var(--font-brand);
  font-size: clamp(1.4rem, 2.1vw, 1.8rem);
  font-weight: 700;
  line-height: 1.3;
}

.about-story-team-principles {
  display: grid;
  grid-template-columns: minmax(0, 0.7fr) minmax(0, 1.3fr);
  gap: clamp(30px, 5vw, 90px);
  margin-top: 88px;
}

.about-story-principles-heading h3 {
  max-width: 420px;
  font-size: clamp(2.2rem, 3vw, 3.1rem);
}

.about-story-principles-heading p {
  margin-top: 16px;
  color: #514c44;
  font-size: 1.04rem;
}

.about-story-checklist,
.about-story-reflection ul {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px 24px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.about-story-checklist li {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  color: #3f3a33;
  font-size: 0.98rem;
  line-height: 1.55;
}

.about-story-checklist li span {
  display: grid;
  width: 25px;
  height: 25px;
  flex: 0 0 25px;
  place-items: center;
  border-radius: 50%;
  background: #e8d1a0;
  color: #604218;
  font-weight: 900;
}

.about-story-reflection {
  display: grid;
  grid-template-columns: minmax(0, 0.95fr) minmax(0, 1.05fr);
  gap: 40px;
  margin-top: 70px;
  border: 1px solid #ead9b8;
  border-radius: 20px;
  background: #fffefa;
  padding: 38px;
  box-shadow: 0 12px 32px rgba(23, 21, 17, 0.06);
}

.about-story-reflection h3 {
  max-width: 570px;
  margin-top: 10px;
  color: var(--home-navy);
  font-family: var(--font-brand);
  font-size: clamp(1.5rem, 2vw, 2rem);
  line-height: 1.25;
}

.about-story-reflection p {
  margin-top: 12px;
  color: #514c44;
}

.about-story-reflection ul {
  gap: 12px;
}

.about-story-reflection li {
  display: flex;
  min-height: 74px;
  align-items: center;
  border-radius: 12px;
  background: #f8f1e2;
  color: var(--home-gold-text);
  padding: 16px;
  font-family: var(--font-brand);
  font-size: 1.05rem;
  font-weight: 700;
  line-height: 1.3;
}

.about-story-conclusion {
  max-width: 840px;
  margin: 42px auto 0 !important;
  color: #514c44;
  font-size: 1.05rem;
  line-height: 1.7;
  text-align: center;
}

.about-story-promise {
  background: radial-gradient(circle at 88% 10%, #3d2c19, transparent 38%), #171511;
  color: #fffaf0;
  padding: 88px 0 80px;
  text-align: center;
}

.about-story-promise > .about-story-container {
  max-width: 1100px;
}

.about-story-promise-kicker {
  color: #e8c77b;
  font-size: 0.78rem;
  font-weight: 900;
  text-transform: uppercase;
}

.about-story-promise h2 {
  max-width: 950px;
  margin: 18px auto 38px;
  color: #fffaf0;
}

.about-story-promise h2 span {
  color: #e8c77b;
}

.about-story-promise-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.about-story-promise-grid p {
  display: grid;
  min-height: 84px;
  place-items: center;
  border: 1px solid rgba(232, 199, 123, 0.3);
  border-radius: 12px;
  background: rgba(255, 250, 240, 0.05);
  color: #fffaf0;
  padding: 16px;
  font-size: 1rem;
  line-height: 1.4;
}

.about-story-promise-closing {
  margin: 44px 0 30px !important;
  color: #e8c77b;
  font-family: var(--font-brand);
  font-size: clamp(1.3rem, 2vw, 1.7rem);
  line-height: 1.45;
}

.about-story-signature {
  display: grid;
  gap: 8px;
  max-width: 650px;
  margin: 0 auto;
  border-top: 1px solid rgba(232, 199, 123, 0.3);
  padding-top: 26px;
}

.about-story-signature strong {
  color: #fffaf0;
  font-family: var(--font-brand);
  font-size: 1.2rem;
}

.about-story-signature span {
  color: #dec997;
  font-size: 0.94rem;
  font-style: italic;
}

@media (max-width: 1080px) {
  .about-story-value-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .about-story-team-intro,
  .about-story-team-principles {
    grid-template-columns: 1fr;
  }

  .about-story-team-image {
    height: 420px;
  }

  .about-story-team-principles {
    margin-top: 70px;
  }
}

@media (max-width: 700px) {
  .about-story-container {
    width: min(100% - 32px, 560px);
  }

  .about-story-values,
  .about-story-team,
  .about-story-promise {
    scroll-margin-top: 68px;
  }

  .about-story-values {
    padding: 64px 0;
  }

  .about-story h2 {
    font-size: clamp(2.15rem, 9vw, 3rem);
  }

  .about-story-heading {
    margin-bottom: 28px;
  }

  .about-story-heading > p {
    font-size: 1rem;
  }

  .about-story-value-grid,
  .about-story-checklist,
  .about-story-reflection,
  .about-story-reflection ul,
  .about-story-promise-grid {
    grid-template-columns: 1fr;
  }

  .about-story-value-grid {
    gap: 12px;
  }

  .about-story-value-card {
    padding: 22px;
  }

  .about-story-value-card h3 {
    margin-top: 16px;
  }

  .about-story-team {
    padding: 64px 0;
  }

  .about-story-team-image {
    height: 300px;
  }

  .about-story-team-intro {
    gap: 28px;
  }

  .about-story-team-principles {
    gap: 26px;
    margin-top: 56px;
  }

  .about-story-checklist {
    gap: 16px;
  }

  .about-story-reflection {
    gap: 24px;
    margin-top: 52px;
    padding: 24px;
  }

  .about-story-reflection li {
    min-height: 0;
  }

  .about-story-promise {
    padding: 70px 0 64px;
  }

  .about-story-promise-grid p {
    min-height: 62px;
  }
}
</style>
