<template>
  <Teleport to="body">
    <transition name="hug-fade">
      <div
        v-if="open"
        class="hug-backdrop"
        @click.self="close"
      >
        <div
          ref="modalRef"
          class="hug-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="hug-title"
          aria-describedby="hug-intro"
          @keydown.esc.stop.prevent="close"
          @keydown="onKeydown"
        >
          <!-- ── Header ── -->
          <div class="hug-header">
            <div class="hug-header-text">
              <h2 id="hug-title" class="hug-title">Love what we're building? Help us grow.</h2>
              <p id="hug-intro" class="hug-intro">
                A quick share, a GitHub star, or a recommendation can make a real
                difference. Help more people discover our projects and keep
                development moving.
              </p>
            </div>
            <button
              ref="closeBtnRef"
              class="hug-close"
              type="button"
              aria-label="Close"
              @click="close"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>

          <!-- ── Scrollable body ── -->
          <div class="hug-body">

            <!-- 1 ── SHARE THE PROJECT (primary action, above the fold) -->
            <section class="hug-section hug-section--hero" aria-labelledby="hug-share-h">
              <div class="hug-section-head">
                <span class="hug-step">1</span>
                <h3 id="hug-share-h" class="hug-section-title">Share the project</h3>
              </div>
              <p class="hug-section-desc">
                Know someone who could use this? Share it with your team, another
                business owner, or your favorite IT community.
              </p>

              <div class="hug-hero-actions">
                <button type="button" class="hug-btn hug-btn--primary hug-btn--lg" @click="shareProject">
                  <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>
                  Share This Project
                </button>
                <button type="button" class="hug-btn hug-btn--outline hug-btn--lg" @click="copy(project.publicUrl, 'link', 'Link copied!')">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
                  {{ copied === 'link' ? 'Link copied!' : 'Copy Link' }}
                </button>
                <button type="button" class="hug-btn hug-btn--outline hug-btn--lg" @click="copy(shareMessage, 'msg', 'Message copied!')">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                  {{ copied === 'msg' ? 'Message copied!' : 'Copy Ready-to-Post Message' }}
                </button>
              </div>

              <!-- The exact text that gets copied/shared, so nothing is a surprise -->
              <div class="hug-preview">
                <div class="hug-preview-label">Ready-to-post message</div>
                <p class="hug-preview-text">{{ shareMessage }}</p>
              </div>

              <div class="hug-networks" role="group" aria-label="Share on a network">
                <span class="hug-networks-label">Or share on</span>
                <button type="button" class="hug-net" @click="openShare(projectTargets.linkedin)" aria-label="Share on LinkedIn">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M4.98 3.5a2.5 2.5 0 11-.02 5 2.5 2.5 0 01.02-5zM2 9h6v12H2zM9 9h5.7v1.7h.08c.8-1.3 2.3-2 4-2 3.2 0 4.2 2 4.2 5.2V21h-6v-6c0-1.4-.5-2.4-1.8-2.4-1.1 0-1.8.7-2.1 1.5-.1.2-.1.6-.1.9V21H9z"/></svg>
                  LinkedIn
                </button>
                <button type="button" class="hug-net" @click="openShare(projectTargets.facebook)" aria-label="Share on Facebook">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M22 12a10 10 0 10-11.6 9.9v-7H7.9V12h2.5V9.8c0-2.5 1.5-3.9 3.8-3.9 1.1 0 2.2.2 2.2.2v2.4h-1.2c-1.2 0-1.6.75-1.6 1.5V12h2.7l-.43 2.9h-2.27v7A10 10 0 0022 12z"/></svg>
                  Facebook
                </button>
                <button type="button" class="hug-net" @click="openShare(projectTargets.x)" aria-label="Share on X">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><path d="M18.9 2H22l-6.8 7.8L22.8 22h-6.5l-5-6.6L5.5 22H2.4l7.1-8.1L1.6 2h6.6l4.7 6.2zm-1.1 18h1.7L6.4 3.7H4.6z"/></svg>
                  X
                </button>
                <button type="button" class="hug-net" @click="openShare(projectTargets.email)" aria-label="Share by email">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="4" width="20" height="16" rx="2"/><polyline points="22,6 12,13 2,6"/></svg>
                  Email
                </button>
              </div>
            </section>

            <!-- 2 ── OTHER PROJECTS -->
            <section class="hug-section" aria-labelledby="hug-proj-h">
              <div class="hug-section-head">
                <span class="hug-step">2</span>
                <h3 id="hug-proj-h" class="hug-section-title">Discover &amp; share our other projects</h3>
              </div>
              <p class="hug-section-desc">
                Help spread the word about the other tools and services we're building.
              </p>

              <div class="hug-cards">
                <div v-for="p in otherProjects" :key="p.url" class="hug-card">
                  <div class="hug-card-main">
                    <div class="hug-card-name">{{ p.name }}</div>
                    <div class="hug-card-url">{{ displayUrl(p.url) }}</div>
                    <p v-if="p.description" class="hug-card-desc">{{ p.description }}</p>
                  </div>
                  <div class="hug-card-actions">
                    <button type="button" class="hug-btn hug-btn--primary hug-btn--sm" @click="shareOther(p)">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>
                      Share
                    </button>
                    <button type="button" class="hug-btn hug-btn--outline hug-btn--sm" @click="copy(p.url, 'p-' + p.url, 'Link copied!')">
                      {{ copied === 'p-' + p.url ? 'Link copied!' : 'Copy Link' }}
                    </button>
                    <a :href="p.url" target="_blank" rel="noopener noreferrer" class="hug-btn hug-btn--ghost hug-btn--sm">
                      Visit
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="7" y1="17" x2="17" y2="7"/><polyline points="7 7 17 7 17 17"/></svg>
                    </a>
                  </div>
                </div>
              </div>

              <div class="hug-preview hug-preview--inset">
                <div class="hug-preview-label">Ready-to-copy network message</div>
                <p class="hug-preview-text">{{ networkMessage }}</p>
                <button type="button" class="hug-btn hug-btn--outline hug-btn--sm" @click="copy(networkMessage, 'net', 'Message copied!')">
                  {{ copied === 'net' ? 'Message copied!' : 'Copy Message' }}
                </button>
              </div>
            </section>

            <!-- 3 ── GITHUB -->
            <section class="hug-section" aria-labelledby="hug-gh-h">
              <div class="hug-section-head">
                <span class="hug-step">3</span>
                <h3 id="hug-gh-h" class="hug-section-title">Star &amp; explore on GitHub</h3>
              </div>
              <p class="hug-section-desc">
                A GitHub star helps others discover the project. Explore the code,
                follow development, and share your favorites.
              </p>
              <div class="hug-inline-actions">
                <a v-if="project.repoUrl" :href="project.repoUrl" target="_blank" rel="noopener noreferrer" class="hug-btn hug-btn--star">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
                  Star This Project
                </a>
                <a :href="githubProfileUrl" target="_blank" rel="noopener noreferrer" class="hug-btn hug-btn--outline">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 .3a12 12 0 00-3.8 23.4c.6.1.8-.3.8-.6v-2.2c-3.3.7-4-1.6-4-1.6-.6-1.4-1.3-1.8-1.3-1.8-1.1-.7.1-.7.1-.7 1.2.1 1.8 1.2 1.8 1.2 1 1.8 2.8 1.3 3.5 1 .1-.8.4-1.3.7-1.6-2.7-.3-5.5-1.3-5.5-6 0-1.2.5-2.3 1.2-3.1-.1-.3-.5-1.5.1-3.2 0 0 1-.3 3.3 1.2a11.5 11.5 0 016 0C17.1 4.7 18.1 5 18.1 5c.6 1.7.2 2.9.1 3.2.8.8 1.2 1.9 1.2 3.1 0 4.7-2.8 5.7-5.5 6 .4.4.8 1.1.8 2.2v3.3c0 .3.2.7.8.6A12 12 0 0012 .3"/></svg>
                  Explore Our GitHub
                </a>
              </div>
              <p class="hug-hint">The star button is at the top of the repository page.</p>
            </section>

            <!-- 4 ── SPONSOR (only when a destination is configured) -->
            <section v-if="sponsorUrl" class="hug-section" aria-labelledby="hug-sponsor-h">
              <div class="hug-section-head">
                <span class="hug-step">4</span>
                <h3 id="hug-sponsor-h" class="hug-section-title">Sponsor development</h3>
              </div>
              <p class="hug-section-desc">
                Want to help fund ongoing development, improvements, and
                maintenance? Consider becoming a sponsor.
              </p>
              <div class="hug-inline-actions">
                <a :href="sponsorUrl" target="_blank" rel="noopener noreferrer" class="hug-btn hug-btn--sponsor">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>
                  Sponsor Development
                </a>
              </div>
            </section>

            <!-- 5 ── SUPPORT OUR BUSINESS -->
            <section class="hug-section" aria-labelledby="hug-biz-h">
              <div class="hug-section-head">
                <span class="hug-step">{{ sponsorUrl ? 5 : 4 }}</span>
                <h3 id="hug-biz-h" class="hug-section-title">Support our business</h3>
              </div>
              <p class="hug-section-desc">
                Need IT services or know a business that does? Visit
                {{ business.name }} or recommend us to someone who could use a hand.
              </p>
              <div class="hug-inline-actions">
                <a :href="business.url" target="_blank" rel="noopener noreferrer" class="hug-btn hug-btn--primary">
                  Visit {{ business.name }}
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="7" y1="17" x2="17" y2="7"/><polyline points="7 7 17 7 17 17"/></svg>
                </a>
                <button type="button" class="hug-btn hug-btn--outline" @click="shareBusiness">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>
                  Share {{ business.name }}
                </button>
              </div>
              <a :href="business.facebookUrl" target="_blank" rel="noopener noreferrer" class="hug-secondary-link">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M22 12a10 10 0 10-11.6 9.9v-7H7.9V12h2.5V9.8c0-2.5 1.5-3.9 3.8-3.9 1.1 0 2.2.2 2.2.2v2.4h-1.2c-1.2 0-1.6.75-1.6 1.5V12h2.7l-.43 2.9h-2.27v7A10 10 0 0022 12z"/></svg>
                Follow {{ business.name }} on Facebook
              </a>
            </section>

            <!-- Manual-copy fallback, shown only when a clipboard write failed -->
            <div v-if="copyFallback" class="hug-fallback" role="alert">
              <div class="hug-fallback-head">
                Copying was blocked by your browser — select the text below and copy it manually.
              </div>
              <textarea
                ref="fallbackRef"
                class="hug-fallback-text"
                readonly
                rows="3"
                :value="copyFallback"
              ></textarea>
              <button type="button" class="hug-btn hug-btn--ghost hug-btn--sm" @click="copyFallback = ''">Dismiss</button>
            </div>
          </div>

          <!-- ── Footer ── -->
          <div class="hug-footer">
            <p class="hug-closing">
              Every share, recommendation, star, and contribution helps. Thanks
              for being part of what we're building.
            </p>
            <button type="button" class="hug-btn hug-btn--ghost" @click="close">Close</button>
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<script>
import { ref, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import {
  CURRENT_PROJECT,
  OTHER_PROJECTS,
  NETWORK_SHARE_MESSAGE,
  BUSINESS,
  SPONSOR_URL,
  GITHUB_PROFILE_URL,
  buildProjectShareMessage,
} from '@/config/projects'
import { copyToClipboard } from '@/utils/clipboard'
import { nativeShare, shareTargets, openShareWindow, canNativeShare } from '@/utils/share'

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])'

export default {
  name: 'HelpUsGrowModal',
  props: {
    open: { type: Boolean, default: false },
  },
  emits: ['close'],
  setup(props, { emit }) {
    const modalRef = ref(null)
    const closeBtnRef = ref(null)
    const fallbackRef = ref(null)
    const copied = ref('')
    const copyFallback = ref('')
    let copiedTimer = null
    let lastFocused = null

    const project = CURRENT_PROJECT
    const otherProjects = OTHER_PROJECTS
    const networkMessage = NETWORK_SHARE_MESSAGE
    const business = BUSINESS
    const sponsorUrl = SPONSOR_URL
    const githubProfileUrl = GITHUB_PROFILE_URL

    const shareMessage = computed(() => buildProjectShareMessage(project))
    const projectTargets = computed(() =>
      shareTargets({
        url: project.publicUrl,
        text: shareMessage.value,
        subject: `Thought you might find ${project.name} useful`,
      })
    )

    const displayUrl = (url) => url.replace(/^https?:\/\//, '').replace(/\/$/, '')

    const close = () => emit('close')

    // ── Copy with honest success reporting ──────────────────────────────────
    const copy = async (text, key, successLabel) => {
      const ok = await copyToClipboard(text)
      if (ok) {
        copyFallback.value = ''
        copied.value = key
        window.$toast?.success(successLabel)
        clearTimeout(copiedTimer)
        copiedTimer = setTimeout(() => { copied.value = '' }, 2200)
      } else {
        // No success message — offer the text for manual copying instead.
        copied.value = ''
        copyFallback.value = text
        await nextTick()
        fallbackRef.value?.focus()
        fallbackRef.value?.select()
      }
    }

    // ── Sharing ─────────────────────────────────────────────────────────────
    // Native sheet where available; otherwise fall back to copying the message
    // so the user always ends up with something they can paste and send.
    const shareVia = async (title, text, url, fallbackKey) => {
      const result = await nativeShare({ title, text, url })
      if (result === 'shared' || result === 'dismissed') return
      await copy(text, fallbackKey, 'Message copied!')
    }

    const shareProject = () =>
      shareVia(project.name, shareMessage.value, project.publicUrl, 'msg')

    const shareOther = (p) =>
      shareVia(p.name, p.shareMessage, p.url, 'p-' + p.url)

    const shareBusiness = () =>
      shareVia(business.name, business.shareMessage, business.url, 'biz')

    const openShare = (href) => openShareWindow(href)

    // ── Focus trap ──────────────────────────────────────────────────────────
    const onKeydown = (e) => {
      if (e.key !== 'Tab' || !modalRef.value) return
      const items = Array.from(modalRef.value.querySelectorAll(FOCUSABLE))
        .filter((el) => el.offsetParent !== null || el === document.activeElement)
      if (!items.length) return
      const first = items[0]
      const last = items[items.length - 1]
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    }

    // ── Open/close lifecycle: scroll lock + focus restore ───────────────────
    watch(
      () => props.open,
      async (isOpen) => {
        if (isOpen) {
          lastFocused = document.activeElement
          copied.value = ''
          copyFallback.value = ''
          document.body.style.overflow = 'hidden'
          await nextTick()
          closeBtnRef.value?.focus()
        } else {
          document.body.style.overflow = ''
          // Return focus to whatever opened the modal.
          if (lastFocused && typeof lastFocused.focus === 'function') lastFocused.focus()
          lastFocused = null
        }
      }
    )

    onBeforeUnmount(() => {
      document.body.style.overflow = ''
      clearTimeout(copiedTimer)
    })

    return {
      modalRef, closeBtnRef, fallbackRef,
      project, otherProjects, networkMessage, business, sponsorUrl, githubProfileUrl,
      shareMessage, projectTargets, copied, copyFallback,
      close, copy, shareProject, shareOther, shareBusiness, openShare,
      onKeydown, displayUrl, canNativeShare,
    }
  },
}
</script>

<style scoped>
/* Sits below the toast container (9999) so copy confirmations stay visible. */
.hug-backdrop {
  position: fixed;
  inset: 0;
  z-index: 9990;
  /*
    Deliberately NO backdrop-filter here, unlike the smaller shortcuts and
    error-boundary modals. Compositing a blur over the full dashboard stretched
    a declared 200ms dismissal to ~880ms of starved frames; without it the
    modal closes in ~370ms (both measured, Chromium @1440x900 on the Dashboard
    route). Reducing the radius, `will-change: opacity` and `contain: paint`
    were all measured and none of them helped — only dropping the blur did.
    The scrim is darkened to compensate for the lost separation.
  */
  background: rgba(0, 0, 0, 0.72);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
}

.hug-modal {
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.45);
  width: 100%;
  max-width: 760px;
  max-height: calc(100vh - 3rem);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ── Header ── */
.hug-header {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  padding: 1.5rem 1.75rem 1.25rem;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.hug-header-text { flex: 1; min-width: 0; }

.hug-title {
  margin: 0 0 0.5rem;
  font-size: 1.3rem;
  font-weight: 700;
  line-height: 1.3;
  color: var(--text-primary);
}

.hug-intro {
  margin: 0;
  font-size: 0.875rem;
  line-height: 1.55;
  color: var(--text-secondary);
}

.hug-close {
  flex-shrink: 0;
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--text-muted);
  transition: color 0.15s, background 0.15s, border-color 0.15s;
}

.hug-close:hover {
  color: var(--text-primary);
  background: var(--background);
  border-color: var(--text-muted);
}

/* ── Body ── */
.hug-body {
  padding: 1.25rem 1.75rem 1.5rem;
  overflow-y: auto;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.hug-section {
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 1.25rem;
  background: var(--background);
}

/* The share card is the primary action — lift it visually. */
.hug-section--hero {
  background: var(--surface);
  border-color: color-mix(in srgb, var(--primary-color) 45%, var(--border-color));
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--primary-color) 18%, transparent),
              0 6px 20px rgba(0, 0, 0, 0.07);
}

.hug-section-head {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.4rem;
}

.hug-step {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--primary-color);
  color: #fff;
  font-size: 0.72rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.hug-section-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 650;
  color: var(--text-primary);
}

.hug-section-desc {
  margin: 0 0 1rem;
  font-size: 0.85rem;
  line-height: 1.55;
  color: var(--text-secondary);
}

.hug-hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  margin-bottom: 1rem;
}

/* ── Buttons ── */
.hug-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.45rem;
  border-radius: 8px;
  border: 1px solid transparent;
  padding: 0.5rem 0.9rem;
  font-size: 0.82rem;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  text-decoration: none;
  white-space: nowrap;
  transition: background 0.15s, border-color 0.15s, color 0.15s, transform 0.1s;
}

.hug-btn:active:not(:disabled) { transform: translateY(1px); }

.hug-btn:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}

.hug-btn--lg { padding: 0.65rem 1.1rem; font-size: 0.875rem; }
.hug-btn--sm { padding: 0.35rem 0.7rem; font-size: 0.75rem; }

.hug-btn--primary {
  background: var(--primary-color);
  color: #fff;
}
.hug-btn--primary:hover { background: var(--primary-hover); }

.hug-btn--outline {
  background: transparent;
  border-color: var(--border-color);
  color: var(--text-primary);
}
.hug-btn--outline:hover {
  border-color: var(--primary-color);
  color: var(--primary-color);
}

.hug-btn--ghost {
  background: transparent;
  color: var(--text-muted);
}
.hug-btn--ghost:hover { color: var(--text-primary); background: var(--background); }

.hug-btn--star {
  background: #f59e0b;
  color: #1c1917;
}
.hug-btn--star:hover { background: #d97706; color: #fff; }

.hug-btn--sponsor {
  background: #db2777;
  color: #fff;
}
.hug-btn--sponsor:hover { background: #be185d; }

/* ── Message preview ── */
.hug-preview {
  border: 1px dashed var(--border-color);
  border-radius: 10px;
  padding: 0.85rem 1rem;
  background: var(--background);
}

.hug-preview--inset {
  margin-top: 1rem;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.75rem;
}

.hug-preview-label {
  font-size: 0.66rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--text-muted);
  margin-bottom: 0.35rem;
}

.hug-preview-text {
  margin: 0;
  font-size: 0.82rem;
  line-height: 1.6;
  color: var(--text-secondary);
  word-break: break-word;
}

/* ── Network row ── */
.hug-networks {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  margin-top: 1rem;
}

.hug-networks-label {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-right: 0.15rem;
}

.hug-net {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 999px;
  padding: 0.35rem 0.8rem;
  font-size: 0.78rem;
  font-weight: 600;
  font-family: inherit;
  color: var(--text-secondary);
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
}

.hug-net:hover {
  border-color: var(--primary-color);
  color: var(--primary-color);
}

.hug-net:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}

/* ── Project cards ── */
.hug-cards {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.hug-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 0.9rem 1rem;
}

.hug-card-main { min-width: 0; flex: 1 1 220px; }

.hug-card-name {
  font-size: 0.9rem;
  font-weight: 650;
  color: var(--text-primary);
}

.hug-card-url {
  font-size: 0.75rem;
  color: var(--primary-color);
  margin-top: 1px;
  word-break: break-all;
}

.hug-card-desc {
  margin: 0.4rem 0 0;
  font-size: 0.8rem;
  line-height: 1.5;
  color: var(--text-secondary);
}

.hug-card-actions {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
}

/* ── Misc ── */
.hug-inline-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
}

.hug-hint {
  margin: 0.7rem 0 0;
  font-size: 0.75rem;
  color: var(--text-muted);
}

.hug-secondary-link {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  margin-top: 0.85rem;
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--text-secondary);
  text-decoration: none;
}

.hug-secondary-link:hover { color: var(--primary-color); text-decoration: underline; }

.hug-secondary-link:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
  border-radius: 4px;
}

/* ── Clipboard fallback ── */
.hug-fallback {
  border: 1px solid var(--warning-color);
  background: color-mix(in srgb, var(--warning-color) 10%, var(--surface));
  border-radius: 10px;
  padding: 0.9rem 1rem;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.6rem;
}

.hug-fallback-head {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-primary);
}

.hug-fallback-text {
  width: 100%;
  font-family: inherit;
  font-size: 0.8rem;
  line-height: 1.5;
  color: var(--text-primary);
  background: var(--bg-input, var(--surface));
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 0.5rem 0.6rem;
  resize: vertical;
}

/* ── Footer ── */
.hug-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem 1.75rem;
  border-top: 1px solid var(--border-color);
  background: var(--background);
  flex-shrink: 0;
}

.hug-closing {
  margin: 0;
  font-size: 0.8rem;
  line-height: 1.5;
  color: var(--text-secondary);
}

/* ── Transition ── */
.hug-fade-enter-active, .hug-fade-leave-active { transition: opacity 0.2s ease; }
.hug-fade-enter-from, .hug-fade-leave-to { opacity: 0; }


.hug-fade-enter-active .hug-modal { animation: hug-modal-in 0.22s ease; }

@keyframes hug-modal-in {
  from { opacity: 0; transform: scale(0.97) translateY(-8px); }
  to   { opacity: 1; transform: scale(1) translateY(0); }
}

@media (prefers-reduced-motion: reduce) {
  .hug-fade-enter-active, .hug-fade-leave-active { transition: none; }
  .hug-fade-enter-active .hug-modal { animation: none; }
  .hug-btn:active:not(:disabled) { transform: none; }
}

/* ── Mobile ── */
@media (max-width: 768px) {
  .hug-backdrop { padding: 0; align-items: stretch; }

  .hug-modal {
    max-width: 100%;
    max-height: 100vh;
    border-radius: 0;
    border: none;
  }

  .hug-header { padding: 1.15rem 1.15rem 1rem; }
  .hug-title { font-size: 1.1rem; }
  .hug-body { padding: 1rem 1.15rem 1.25rem; gap: 1rem; }
  .hug-section { padding: 1rem; }

  /* Full-width stacked actions are easier to hit on a phone. */
  .hug-hero-actions { flex-direction: column; align-items: stretch; }
  .hug-hero-actions .hug-btn { width: 100%; }

  .hug-card { flex-direction: column; align-items: stretch; }
  .hug-card-actions { justify-content: flex-start; }

  .hug-footer {
    flex-direction: column;
    align-items: stretch;
    padding: 1rem 1.15rem;
    padding-bottom: calc(1rem + env(safe-area-inset-bottom, 0px));
  }
  .hug-footer .hug-btn { width: 100%; }
  .hug-closing { text-align: center; }
}
</style>
