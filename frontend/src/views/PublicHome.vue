<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import {
  ArrowRight,
  BadgePlus,
  Building2,
  CalendarCheck2,
  CalendarDays,
  Check,
  CircleUserRound,
  ClipboardPlus,
  Eye,
  Gift,
  Heart,
  HeartHandshake,
  House,
  Info,
  LayoutDashboard,
  LogIn,
  LogOut,
  MessageCircle,
  Menu,
  MonitorSmartphone,
  Quote,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Star,
  Tag,
  Target,
  UserPlus,
  UsersRound,
  X,
} from "lucide-vue-next";

import AppointmentForm from "../components/AppointmentForm.vue";
import AuthModal from "../components/AuthModal.vue";
import BaseModal from "../components/BaseModal.vue";
import BookingAuthPrompt from "../components/BookingAuthPrompt.vue";
import { apiRequest, refreshSession, session, signOut } from "../services/api";
import { fallbackPromos, fallbackServices, getServiceModalContent } from "../services/constants";
import { dashboardPath, navigate } from "../router";
import { consumeQueuedToast, showToast } from "../services/toast";
import { validatedPayload } from "../services/validation";

const services = ref([]);
const promos = ref([]);
const feedback = ref([]);
const availability = ref([]);
const clinicDoctor = ref("");
const authOpen = ref(false);
const authTab = ref("login");
const authRequiredOpen = ref(false);
const activeSection = ref("home");
const selectedPublicService = ref("");
const selectedService = ref(null);
const bookingOpen = ref(false);
const mobileMenuOpen = ref(false);
const searchOpen = ref(false);
const searchQuery = ref("");
const searchRoot = ref(null);
const searchInput = ref(null);
const mobileMenuClose = ref(null);
const feedbackForm = reactive({ name: "", rating: "5", message: "", _website: "" });
const feedbackBusy = ref(false);
const showAllFeedback = ref(false);
const ratingOptions = [1, 2, 3, 4, 5];

const bookingNote = computed(() => {
  if (session.user?.role === "doctor")
    return "Doctor accounts manage appointments from the dashboard.";
  return session.user
    ? "Your booking will be connected to your patient account."
    : "Browsing is open to everyone. Booking requires a patient account.";
});

const publicBookingLabel = computed(() =>
  session.user?.role === "patient" ? "Review Appointment" : "Continue Booking",
);

const promoCards = computed(() =>
  promos.value.map((promo) => ({ promo, display: promoPresentation(promo) })),
);

const selectedServiceDetails = computed(() =>
  selectedService.value ? getServiceModalContent(selectedService.value) : null,
);

const searchItems = computed(() => [
  ...services.value.map((service) => ({
    id: `service-${service.id || service.name}`,
    kind: "service",
    label: service.name,
    description: service.description,
    meta: "Dental service",
    service,
    searchText: `${service.name} ${service.description} dental service treatment procedure`,
  })),
  ...promos.value.map((promo) => ({
    id: `promo-${promo.id || promo.title}`,
    kind: "promo",
    label: promo.title,
    description: promo.description,
    meta: "Special offer",
    target: "promos",
    searchText: `${promo.title} ${promo.description} promo discount special offer`,
  })),
  {
    id: "page-about",
    kind: "page",
    label: "About BORJA Dental Clinic",
    description: "Clinic values, facilities, and patient-first care.",
    meta: "Page",
    target: "about",
    searchText: "about clinic dentist doctor facilities mission vision values",
  },
  {
    id: "page-feedback",
    kind: "page",
    label: "Patient Feedback",
    description: "Read patient experiences or leave a clinic review.",
    meta: "Page",
    target: "feedback",
    searchText: "feedback reviews rating patient experience",
  },
  {
    id: "action-booking",
    kind: "booking",
    label: "Book an Appointment",
    description: "Choose an available clinic date and time.",
    meta: "Appointment",
    searchText: "book booking appointment schedule date time availability",
  },
]);

const searchResults = computed(() => {
  const query = searchQuery.value.trim().toLowerCase();
  if (!query) return [];
  const words = query.split(/\s+/).filter(Boolean);
  return searchItems.value
    .filter((item) => words.every((word) => item.searchText.toLowerCase().includes(word)))
    .slice(0, 7);
});

const popularSearches = [
  "Teeth Whitening",
  "Traditional Metal Braces",
  "Oral Prophylaxis",
  "Promos",
  "Book Appointment",
];

const visibleFeedback = computed(() =>
  feedback.value.slice(0, showAllFeedback.value ? feedback.value.length : 3),
);

const feedbackRatingLabel = computed(() => {
  const labels = ["", "Needs improvement", "Fair", "Good", "Very good", "Excellent"];
  return labels[Number(feedbackForm.rating)] || "Select a rating";
});

const mobileGreeting = computed(() => {
  const nameParts = String(session.user?.name || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  const firstName = nameParts[0]?.toLowerCase().startsWith("dr") ? nameParts[1] : nameParts[0];
  return firstName ? `Hello, ${firstName}!` : "Hello!";
});

function openAuth(tab = "login") {
  bookingOpen.value = false;
  authRequiredOpen.value = false;
  closeMobileMenu();
  authTab.value = tab;
  authOpen.value = true;
}

function requireBookingAuthentication() {
  bookingOpen.value = false;
  authRequiredOpen.value = true;
}

function continueBookingAuthentication(tab) {
  authRequiredOpen.value = false;
  openAuth(tab);
}

function backToAppointment() {
  authRequiredOpen.value = false;
  requestAnimationFrame(openBooking);
}

function reviewPendingAppointment() {
  bookingOpen.value = false;
  navigate("/appointment-confirmation.html");
}

function closeMobileMenu() {
  mobileMenuOpen.value = false;
  document.body.classList.remove("mobile-nav-open");
}

async function toggleMobileMenu() {
  if (mobileMenuOpen.value) {
    closeMobileMenu();
    return;
  }

  closeSearch();
  mobileMenuOpen.value = true;
  document.body.classList.add("mobile-nav-open");
  await nextTick();
  mobileMenuClose.value?.focus();
}

function openDashboard() {
  closeMobileMenu();
  navigate(dashboardPath(session.user.role));
}

async function toggleSearch() {
  if (!searchOpen.value) closeMobileMenu();
  searchOpen.value = !searchOpen.value;
  if (searchOpen.value) {
    await nextTick();
    searchInput.value?.focus();
  }
}

function closeSearch() {
  searchOpen.value = false;
  searchQuery.value = "";
}

function setPopularSearch(term) {
  searchQuery.value = term;
  nextTick(() => searchInput.value?.focus());
}

function goToSection(sectionId) {
  closeMobileMenu();
  window.location.hash = sectionId;
  document.getElementById(sectionId)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function selectSearchResult(result) {
  closeSearch();
  if (result.kind === "service") {
    goToSection("services");
    selectedService.value = result.service;
    return;
  }
  if (result.kind === "booking") {
    openBooking();
    return;
  }
  goToSection(result.target);
}

function selectFirstSearchResult() {
  if (searchResults.value[0]) selectSearchResult(searchResults.value[0]);
}

function onDocumentPointerDown(event) {
  if (searchOpen.value && !searchRoot.value?.contains(event.target)) closeSearch();
}

function onDocumentKeydown(event) {
  if (event.key !== "Escape") return;
  if (searchOpen.value) closeSearch();
  if (mobileMenuOpen.value) closeMobileMenu();
}

function syncActiveSection() {
  activeSection.value = window.location.hash.slice(1) || "home";
}

function scrollToBooking() {
  document
    .querySelector(".appointment-panel")
    ?.scrollIntoView({ behavior: "smooth", block: "center" });
}

function openBooking() {
  closeMobileMenu();
  if (window.matchMedia("(max-width: 640px)").matches) {
    bookingOpen.value = true;
    return;
  }
  scrollToBooking();
}

function bookService(serviceName) {
  selectedPublicService.value = serviceName;
  openBooking();
}

function openServiceDetails(service) {
  selectedService.value = service;
}

function bookSelectedService() {
  const serviceName = selectedService.value?.name;
  selectedService.value = null;
  if (serviceName) requestAnimationFrame(() => bookService(serviceName));
}

function feedbackInitials(name = "") {
  const initials = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("");
  return initials || "P";
}

function formatFeedbackDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Recent visit";
  return new Intl.DateTimeFormat("en-PH", {
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

function serviceArt(serviceName = "") {
  const name = serviceName.toLowerCase();
  if (
    name.includes("brace") ||
    name.includes("orthodont") ||
    name.includes("aligner") ||
    name.includes("retainer") ||
    name.includes("space maintainer") ||
    name.includes("expander")
  )
    return "art-braces";
  if (name.includes("extract") || name.includes("odontectomy")) return "art-extraction";
  if (name.includes("prophylaxis") || name.includes("clean")) return "art-cleaning";
  if (name.includes("root canal") || name.includes("apicoectomy")) return "art-root-canal";
  if (name.includes("whitening")) return "art-whitening";
  if (name.includes("restoration") || name.includes("veneer")) return "art-restoration";
  if (name.includes("filling")) return "art-filling";
  if (name.includes("bridge") || name.includes("denture")) return "art-bridge";
  if (name.includes("crown")) return "art-crown";
  if (name.includes("x-ray") || name.includes("xray")) return "art-xray";
  if (name.includes("sealant") || name.includes("fluoride") || name.includes("gingiv"))
    return "art-preventive";
  return "art-consultation";
}

function promoPresentation(promo) {
  const title = (promo.title || "").toLowerCase();
  if (title.includes("family")) {
    return {
      badge: "Limited time",
      highlight: "15% OFF",
      icon: UsersRound,
      tone: "aqua",
      service: "Oral Prophylaxis",
      benefits: ["General checkup", "Oral cleaning", "Dental consultation"],
    };
  }
  if (title.includes("new patient")) {
    return {
      badge: "New patients",
      highlight: "FREE ASSESSMENT",
      icon: BadgePlus,
      tone: "mint",
      service: "Oral Prophylaxis",
      benefits: ["Initial consultation", "Oral examination", "Personalized treatment plan"],
    };
  }
  if (title.includes("whitening")) {
    return {
      badge: "Special package",
      highlight: "SPECIAL PRICE",
      icon: Sparkles,
      tone: "rose",
      service: "Teeth Whitening",
      benefits: ["Dental consultation", "Professional teeth whitening", "Aftercare guide"],
    };
  }
  return {
    badge: "Special offer",
    highlight: "PROMO",
    icon: Gift,
    tone: "aqua",
    service: "Oral Prophylaxis",
    benefits: ["Quality dental care", "Patient-focused service", "Limited clinic offer"],
  };
}

async function loadPublicData() {
  const requests = await Promise.allSettled([
    apiRequest("/api/services"),
    apiRequest("/api/promos"),
    apiRequest("/api/feedback"),
    apiRequest("/api/availability"),
  ]);
  services.value =
    requests[0].status === "fulfilled" && requests[0].value.services?.length
      ? requests[0].value.services
      : fallbackServices;
  promos.value =
    requests[1].status === "fulfilled" && requests[1].value.promos?.length
      ? requests[1].value.promos
      : fallbackPromos;
  feedback.value = requests[2].status === "fulfilled" ? requests[2].value.feedback || [] : [];
  if (requests[3].status === "fulfilled") {
    availability.value = requests[3].value.availability || [];
    clinicDoctor.value = requests[3].value.clinic_doctor || availability.value[0]?.doctor || "";
  }
}

async function logout() {
  closeMobileMenu();
  try {
    await signOut();
    showToast("Logged out.");
  } catch (error) {
    showToast(error.message, "error");
  }
}

function bookingCreated() {
  bookingOpen.value = false;
  navigate("/patient-dashboard.html");
}

async function submitFeedback() {
  feedbackBusy.value = true;
  try {
    const payload = validatedPayload({ ...feedbackForm });
    const data = await apiRequest("/api/feedback", { method: "POST", body: payload });
    feedback.value.unshift(data.feedback);
    Object.assign(feedbackForm, { name: "", rating: "5", message: "", _website: "" });
    showToast("Thank you for the feedback.");
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    feedbackBusy.value = false;
  }
}

onMounted(async () => {
  syncActiveSection();
  window.addEventListener("hashchange", syncActiveSection);
  document.addEventListener("pointerdown", onDocumentPointerDown);
  document.addEventListener("keydown", onDocumentKeydown);
  consumeQueuedToast();
  try {
    await refreshSession();
  } catch (error) {
    showToast(error.message, "error");
  }
  await loadPublicData();
  const params = new URLSearchParams(window.location.search);
  if (params.get("login") === "1") openAuth("login");
  else if (params.get("edit-booking") === "1") requestAnimationFrame(openBooking);
});

onBeforeUnmount(() => {
  window.removeEventListener("hashchange", syncActiveSection);
  document.removeEventListener("pointerdown", onDocumentPointerDown);
  document.removeEventListener("keydown", onDocumentKeydown);
  document.body.classList.remove("mobile-nav-open");
});
</script>

<template>
  <header class="site-header" :class="{ 'mobile-menu-open': mobileMenuOpen }">
    <a class="brand" href="#home" aria-label="BORJA Dental Clinic home">
      <img class="brand-logo" src="/assets/logo.png" alt="" />
      <span><strong>BORJA</strong><small>Dental Clinic</small></span>
    </a>
    <nav class="main-nav" aria-label="Main navigation">
      <a :class="{ active: activeSection === 'home' }" href="#home">Home</a>
      <a :class="{ active: activeSection === 'about' }" href="#about">About</a>
      <a :class="{ active: activeSection === 'services' }" href="#services">Services</a>
      <a :class="{ active: activeSection === 'promos' }" href="#promos">Promos</a>
      <a :class="{ active: activeSection === 'feedback' }" href="#feedback">Feedback</a>
      <button class="nav-action" type="button" @click="openBooking">Book Appointment</button>
    </nav>
    <div class="auth-actions">
      <div ref="searchRoot" class="site-search">
        <button
          class="site-search-toggle"
          type="button"
          aria-label="Search website"
          aria-controls="siteSearchPanel"
          :aria-expanded="searchOpen"
          @click="toggleSearch"
        >
          <Search :size="21" aria-hidden="true" />
        </button>

        <section
          v-if="searchOpen"
          id="siteSearchPanel"
          class="site-search-panel"
          aria-label="Website search"
        >
          <form class="site-search-form" role="search" @submit.prevent="selectFirstSearchResult">
            <div class="site-search-input">
              <Search :size="20" aria-hidden="true" />
              <input
                ref="searchInput"
                v-model="searchQuery"
                type="search"
                autocomplete="off"
                spellcheck="false"
                aria-label="Search services, promos, or pages"
                placeholder="Search services, promos, or pages"
              />
              <button
                v-if="searchQuery"
                class="site-search-clear"
                type="button"
                aria-label="Clear search"
                @click="searchQuery = ''"
              >
                <X :size="17" aria-hidden="true" />
              </button>
            </div>
            <button
              class="site-search-close"
              type="button"
              aria-label="Close search"
              @click="closeSearch"
            >
              <X :size="21" aria-hidden="true" />
            </button>
          </form>

          <div v-if="!searchQuery.trim()" class="site-search-popular-layout">
            <div class="site-search-popular">
              <h2>Popular searches</h2>
              <button
                v-for="term in popularSearches"
                :key="term"
                type="button"
                @click="setPopularSearch(term)"
              >
                <Search :size="17" aria-hidden="true" />
                <span>{{ term }}</span>
              </button>
            </div>
            <aside class="site-search-callout" aria-hidden="true">
              <span class="service-art art-cleaning"></span>
              <strong>Find what you need</strong>
              <span>for a healthier smile.</span>
            </aside>
          </div>

          <div v-else class="site-search-results" aria-live="polite">
            <div v-if="searchResults.length" class="site-search-results-heading">
              <h2>Search results</h2>
              <span>{{ searchResults.length }} found</span>
            </div>
            <button
              v-for="result in searchResults"
              :key="result.id"
              class="site-search-result"
              type="button"
              @click="selectSearchResult(result)"
            >
              <span class="site-search-result-icon" aria-hidden="true">
                <span
                  v-if="result.kind === 'service'"
                  class="service-art"
                  :class="serviceArt(result.label)"
                ></span>
                <Gift v-else-if="result.kind === 'promo'" :size="20" />
                <CalendarDays v-else-if="result.kind === 'booking'" :size="20" />
                <MessageCircle v-else-if="result.target === 'feedback'" :size="20" />
                <Building2 v-else :size="20" />
              </span>
              <span class="site-search-result-copy">
                <strong>{{ result.label }}</strong>
                <small>{{ result.description }}</small>
                <em>{{ result.meta }}</em>
              </span>
              <ArrowRight :size="18" aria-hidden="true" />
            </button>

            <div v-if="!searchResults.length" class="site-search-empty">
              <span><Search :size="28" aria-hidden="true" /></span>
              <strong>No results found</strong>
              <p>We could not find anything matching "{{ searchQuery }}".</p>
              <button type="button" @click="searchQuery = ''">View popular searches</button>
            </div>
          </div>
        </section>
      </div>

      <template v-if="!session.user">
        <button class="ghost-button" type="button" @click="openAuth('login')">Log In</button>
        <button class="primary-button" type="button" @click="openAuth('register')">
          <span class="wide-label">Create Account</span>
          <span class="narrow-label">Sign Up</span>
        </button>
      </template>
      <template v-else>
        <button class="ghost-button" type="button" @click="openDashboard">Dashboard</button>
        <button class="danger-button" type="button" @click="logout">Log Out</button>
      </template>
    </div>
    <button
      class="mobile-menu-toggle"
      type="button"
      aria-label="Toggle navigation menu"
      aria-controls="mobileNavigationDrawer"
      :aria-expanded="mobileMenuOpen"
      @click="toggleMobileMenu"
    >
      <Menu :size="27" aria-hidden="true" />
    </button>
  </header>

  <Teleport to="body">
    <div
      v-if="mobileMenuOpen"
      class="mobile-nav-backdrop"
      role="presentation"
      @mousedown.self="closeMobileMenu"
    >
      <aside
        id="mobileNavigationDrawer"
        class="mobile-nav-drawer"
        role="dialog"
        aria-modal="true"
        aria-label="Website navigation"
      >
        <header class="mobile-drawer-header">
          <a class="mobile-drawer-brand" href="#home" @click="closeMobileMenu">
            <img src="/assets/logo.png" alt="" />
            <span><strong>BORJA</strong><small>Dental Clinic</small></span>
          </a>
          <button
            ref="mobileMenuClose"
            class="mobile-drawer-close"
            type="button"
            aria-label="Close navigation menu"
            @click="closeMobileMenu"
          >
            <X :size="27" aria-hidden="true" />
          </button>
        </header>

        <div class="mobile-drawer-greeting">
          <span aria-hidden="true"><CircleUserRound :size="30" /></span>
          <div>
            <strong>{{ mobileGreeting }}</strong>
            <small>Take care of your smile today.</small>
          </div>
        </div>

        <nav class="mobile-drawer-nav" aria-label="Mobile navigation">
          <a :class="{ active: activeSection === 'home' }" href="#home" @click="closeMobileMenu">
            <House :size="23" aria-hidden="true" />
            <span>Home</span>
          </a>
          <a :class="{ active: activeSection === 'about' }" href="#about" @click="closeMobileMenu">
            <Info :size="23" aria-hidden="true" />
            <span>About</span>
          </a>
          <a
            :class="{ active: activeSection === 'services' }"
            href="#services"
            @click="closeMobileMenu"
          >
            <Sparkles :size="23" aria-hidden="true" />
            <span>Services</span>
          </a>
          <a
            :class="{ active: activeSection === 'promos' }"
            href="#promos"
            @click="closeMobileMenu"
          >
            <Tag :size="23" aria-hidden="true" />
            <span>Promos</span>
          </a>
          <a
            :class="{ active: activeSection === 'feedback' }"
            href="#feedback"
            @click="closeMobileMenu"
          >
            <MessageCircle :size="23" aria-hidden="true" />
            <span>Feedback</span>
          </a>
          <button type="button" @click="openBooking">
            <CalendarDays :size="23" aria-hidden="true" />
            <span>Book Appointment</span>
          </button>
        </nav>

        <div class="mobile-drawer-account">
          <template v-if="session.user">
            <button type="button" @click="openDashboard">
              <LayoutDashboard :size="23" aria-hidden="true" />
              <span>Dashboard</span>
            </button>
            <button type="button" @click="logout">
              <LogOut :size="23" aria-hidden="true" />
              <span>Log Out</span>
            </button>
          </template>
          <template v-else>
            <button type="button" @click="openAuth('login')">
              <LogIn :size="23" aria-hidden="true" />
              <span>Log In</span>
            </button>
            <button type="button" @click="openAuth('register')">
              <UserPlus :size="23" aria-hidden="true" />
              <span>Create Account</span>
            </button>
          </template>
        </div>

        <div class="mobile-drawer-feature">
          <div>
            <strong>A Healthier Smile for a Happier You</strong>
            <span>Quality care. Brighter tomorrows.</span>
          </div>
          <span class="mobile-drawer-tooth" aria-hidden="true">
            <span class="service-art art-cleaning"></span>
          </span>
        </div>
      </aside>
    </div>
  </Teleport>

  <main>
    <section id="home" class="hero" aria-labelledby="pageTitle">
      <div class="hero-overlay"></div>
      <div class="hero-content">
        <div class="hero-copy">
          <p class="eyebrow">Your Smile, Our Priority</p>
          <h1 id="pageTitle">Healthy Smiles <span>Brighter Tomorrows</span></h1>
          <p class="hero-text">
            BORJA Dental Clinic is a patient-friendly clinic portal for browsing services, booking
            appointments, and keeping your dental records organized, all in one place.
          </p>
          <div class="hero-actions">
            <button class="primary-button large" type="button" @click="openBooking">
              <CalendarDays :size="19" />
              Book an Appointment
              <ArrowRight :size="18" />
            </button>
            <a class="text-link" href="#about">Learn More</a>
          </div>
          <div class="hero-trust" aria-label="Clinic commitments">
            <div class="trust-item">
              <span><ShieldCheck :size="22" /></span>
              <p><strong>Trusted Care</strong><small>Safe and professional</small></p>
            </div>
            <div class="trust-item">
              <span><UsersRound :size="22" /></span>
              <p><strong>Experienced Dentist</strong><small>Friendly and skilled</small></p>
            </div>
            <div class="trust-item">
              <span><Heart :size="22" /></span>
              <p><strong>Patient First</strong><small>Your comfort matters</small></p>
            </div>
          </div>
        </div>
        <AppointmentForm
          retain-for-authentication
          :services="services"
          :availability="availability"
          :clinic-doctor="clinicDoctor"
          :initial-service="selectedPublicService"
          :submit-label="publicBookingLabel"
          @created="bookingCreated"
          @authentication-required="requireBookingAuthentication"
          @confirmation-required="reviewPendingAppointment"
        >
          <template #note>
            <p class="form-note">{{ bookingNote }}</p>
          </template>
        </AppointmentForm>
      </div>
    </section>

    <section id="about" class="about-showcase">
      <div class="about-intro">
        <div class="about-copy">
          <span class="section-kicker">About us</span>
          <h2>Care that keeps records <span>clear and visits on time.</span></h2>
          <p>
            At BORJA Dental Clinic, we believe that a healthy smile leads to a brighter, more
            confident you. Our clinic provides quality dental care with modern technology, a
            friendly approach, and a patient-first workflow.
          </p>
          <div class="about-trust" aria-label="Clinic qualities">
            <div>
              <span><ShieldCheck :size="22" /></span>
              <p>
                <strong>Trusted &amp; Professional</strong
                ><small>Your oral health is safe with us</small>
              </p>
            </div>
            <div>
              <span><UsersRound :size="22" /></span>
              <p><strong>Friendly Team</strong><small>We care for every smile</small></p>
            </div>
            <div>
              <span><Building2 :size="22" /></span>
              <p>
                <strong>Modern Facilities</strong><small>Comfortable and safe environment</small>
              </p>
            </div>
          </div>
        </div>
        <div class="about-visual">
          <img src="/assets/dental-about-v1.png" alt="Bright modern BORJA dental treatment room" />
          <blockquote>
            <span><Heart :size="22" /></span>
            <p>&ldquo;A healthier smile for a brighter tomorrow.&rdquo;</p>
            <cite>BORJA Dental Clinic</cite>
          </blockquote>
        </div>
      </div>

      <div class="about-feature-grid">
        <article>
          <span class="about-card-index">01</span>
          <MonitorSmartphone class="about-card-icon" :size="42" aria-hidden="true" />
          <div>
            <h3>Patient-first browsing</h3>
            <p>
              Visitors can explore services, promos, clinic details, and feedback without creating
              an account.
            </p>
          </div>
          <ArrowRight class="about-card-arrow" :size="20" aria-hidden="true" />
        </article>
        <article>
          <span class="about-card-index">02</span>
          <CalendarCheck2 class="about-card-icon" :size="42" aria-hidden="true" />
          <div>
            <h3>Login-protected booking</h3>
            <p>
              Appointment reservations are processed only after a patient logs in or creates an
              account.
            </p>
          </div>
          <ArrowRight class="about-card-arrow" :size="20" aria-hidden="true" />
        </article>
        <article>
          <span class="about-card-index">03</span>
          <ClipboardPlus class="about-card-icon" :size="42" aria-hidden="true" />
          <div>
            <h3>Doctor record tools</h3>
            <p>
              The clinic can review appointments and add treatment notes to secure patient records.
            </p>
          </div>
          <ArrowRight class="about-card-arrow" :size="20" aria-hidden="true" />
        </article>
      </div>

      <div class="about-mobile-cta">
        <div>
          <h3>Let&rsquo;s keep your <span>smile healthy!</span></h3>
          <p>Quality care. Brighter tomorrows.</p>
        </div>
        <button class="primary-button" type="button" @click="openBooking">
          Book an Appointment <ArrowRight :size="18" aria-hidden="true" />
        </button>
        <span class="about-mobile-cta-art" aria-hidden="true">
          <span class="service-art art-cleaning"></span>
        </span>
      </div>

      <div class="purpose-band">
        <div class="purpose-heading">
          <span class="section-kicker">Our purpose</span>
          <h2>Our Mission, Vision, and Values</h2>
        </div>
        <div class="purpose-grid">
          <article>
            <span><Target :size="24" /></span>
            <div>
              <h3>Our Mission</h3>
              <p>Deliver dependable dental care through organized, patient-centered service.</p>
            </div>
          </article>
          <article>
            <span><Eye :size="24" /></span>
            <div>
              <h3>Our Vision</h3>
              <p>Make every clinic visit clearer, more comfortable, and easier to manage.</p>
            </div>
          </article>
          <article>
            <span><HeartHandshake :size="24" /></span>
            <div>
              <h3>Our Values</h3>
              <p>Trust, privacy, compassion, professionalism, and responsible care.</p>
            </div>
          </article>
        </div>
      </div>
    </section>

    <section id="services" class="services-showcase">
      <div class="services-banner">
        <div class="services-banner-copy">
          <span class="section-kicker">Our services</span>
          <h2>Complete Dental Care for a <span>Healthier, Brighter You</span></h2>
          <p>
            We offer a wide range of dental services for patients of all ages. Our clinic uses
            modern technology to provide safe, comfortable, and high-quality care.
          </p>
          <p class="services-mobile-tagline" aria-hidden="true">A brighter you,<br />every day.</p>
        </div>
      </div>
      <div class="services-card-grid">
        <article v-for="service in services" :key="service.id || service.name">
          <span class="service-card-icon" aria-hidden="true">
            <span class="service-art" :class="serviceArt(service.name)"></span>
          </span>
          <div>
            <h3>{{ service.name }}</h3>
            <p>{{ service.description }}</p>
            <button type="button" @click="openServiceDetails(service)">
              Learn More <ArrowRight :size="16" />
            </button>
          </div>
        </article>
      </div>
    </section>

    <section id="promos" class="promos-showcase">
      <div class="promos-banner">
        <div class="promos-banner-copy">
          <span class="section-kicker">Special offers</span>
          <h2>
            Healthy Smiles
            <span class="promo-heading-line"><span>for</span> Brighter Days</span>
          </h2>
          <p>
            Take advantage of our current clinic promos and make quality dental care more affordable
            for you and your family.
          </p>
        </div>
      </div>
      <div class="promo-offer-grid">
        <article
          v-for="card in promoCards"
          :key="card.promo.id || card.promo.title"
          :class="`promo-tone-${card.display.tone}`"
        >
          <header>
            <span class="promo-card-icon">
              <component :is="card.display.icon" :size="30" aria-hidden="true" />
            </span>
            <div>
              <span class="promo-label">{{ card.display.badge }}</span>
              <h3>{{ card.promo.title }}</h3>
              <p>{{ card.promo.description }}</p>
            </div>
            <strong>{{ card.display.highlight }}</strong>
          </header>
          <ul>
            <li v-for="benefit in card.display.benefits" :key="benefit">
              <Check :size="15" />{{ benefit }}
            </li>
          </ul>
          <button type="button" @click="bookService(card.display.service)">
            Book Now <ArrowRight :size="17" />
          </button>
        </article>
      </div>
      <div class="promo-cta">
        <div>
          <CalendarDays :size="28" />
          <span
            ><strong>Ready to smile brighter?</strong
            ><small>Book a visit and avail of our latest promos.</small></span
          >
        </div>
        <button class="primary-button" type="button" @click="openBooking">
          Book an Appointment <ArrowRight :size="18" />
        </button>
        <div class="promo-trust" aria-label="Promotion commitments">
          <span><ShieldCheck :size="20" />Safe care</span>
          <span><UsersRound :size="20" />Friendly service</span>
          <span><Heart :size="20" />Patient focused</span>
        </div>
      </div>
    </section>

    <section id="feedback" class="feedback-showcase">
      <div class="feedback-banner">
        <div class="feedback-banner-copy">
          <span class="section-kicker">Patient feedback</span>
          <h2>Patient <span>Experiences.</span></h2>
          <p>
            Real stories from our valued patients. Your feedback helps us grow and continue
            providing dependable dental care.
          </p>
        </div>
      </div>

      <div class="feedback-workspace">
        <div class="feedback-reviews" aria-live="polite">
          <article v-for="item in visibleFeedback" :key="item.id" class="feedback-review-card">
            <div class="feedback-review-avatar" aria-hidden="true">
              {{ feedbackInitials(item.name) }}
            </div>
            <div class="feedback-review-content">
              <header>
                <h3>{{ item.name }}</h3>
                <div class="feedback-review-stars" :aria-label="`${item.rating} out of 5 stars`">
                  <Star
                    v-for="star in ratingOptions"
                    :key="star"
                    :size="18"
                    :fill="star <= Number(item.rating) ? 'currentColor' : 'none'"
                    aria-hidden="true"
                  />
                </div>
                <time :datetime="item.created_at">{{ formatFeedbackDate(item.created_at) }}</time>
              </header>
              <p>&ldquo;{{ item.message }}&rdquo;</p>
            </div>
            <Quote class="feedback-quote" :size="40" aria-hidden="true" />
          </article>

          <div v-if="!feedback.length" class="feedback-empty">
            <MessageCircle :size="24" />
            <span
              ><strong>No feedback yet</strong
              ><small>Be the first to share your experience.</small></span
            >
          </div>

          <button
            v-if="feedback.length > 3"
            class="feedback-more-button"
            type="button"
            @click="showAllFeedback = !showAllFeedback"
          >
            {{ showAllFeedback ? "Show fewer reviews" : "View all reviews" }}
            <ArrowRight :class="{ rotated: showAllFeedback }" :size="17" />
          </button>
        </div>

        <form class="feedback-form feedback-entry-form" @submit.prevent="submitFeedback">
          <label class="hp-field" aria-hidden="true"
            >Website<input v-model="feedbackForm._website" tabindex="-1" autocomplete="off"
          /></label>

          <header class="feedback-form-header">
            <span><MessageCircle :size="25" /></span>
            <div>
              <h3>Share Your Feedback</h3>
              <p>We'd love to hear about your experience.</p>
            </div>
          </header>

          <label
            >Name<input
              v-model="feedbackForm.name"
              minlength="2"
              maxlength="80"
              :disabled="Boolean(session.user)"
              :placeholder="session.user?.name || 'Your name'"
          /></label>

          <fieldset class="feedback-rating-field">
            <legend>Rating</legend>
            <div class="feedback-star-picker">
              <label
                v-for="rating in ratingOptions"
                :key="rating"
                :aria-label="`${rating} star${rating === 1 ? '' : 's'}`"
              >
                <input
                  v-model="feedbackForm.rating"
                  type="radio"
                  name="feedback-rating"
                  :value="String(rating)"
                />
                <Star
                  :size="28"
                  :fill="rating <= Number(feedbackForm.rating) ? 'currentColor' : 'none'"
                  aria-hidden="true"
                />
              </label>
              <span>{{ feedbackRatingLabel }}</span>
            </div>
          </fieldset>

          <label
            >Message<textarea
              v-model="feedbackForm.message"
              rows="5"
              minlength="10"
              maxlength="500"
              required
              placeholder="Write your clinic experience"
            ></textarea>
            <small class="feedback-character-count">{{ feedbackForm.message.length }}/500</small>
          </label>

          <button class="primary-button full" type="submit" :disabled="feedbackBusy">
            <Send :size="18" />
            {{ feedbackBusy ? "Submitting..." : "Submit Feedback" }}
          </button>
        </form>
      </div>

      <div class="feedback-trust" aria-label="Feedback commitments">
        <div>
          <MessageCircle :size="25" />
          <span
            ><strong>Your voice matters</strong
            ><small>Every review helps improve patient care.</small></span
          >
        </div>
        <span><ShieldCheck :size="20" />Listened to securely</span>
        <span><UsersRound :size="20" />Patient-first service</span>
        <span><Heart :size="20" />Care that improves</span>
      </div>
    </section>
  </main>

  <BaseModal
    v-if="bookingOpen"
    title="Book an Appointment"
    size-class="appointment-booking-dialog public-booking-dialog"
    @close="bookingOpen = false"
  >
    <p class="public-booking-subtitle">Quick and easy scheduling</p>
    <AppointmentForm
      compact
      retain-for-authentication
      :services="services"
      :availability="availability"
      :clinic-doctor="clinicDoctor"
      :initial-service="selectedPublicService"
      :submit-label="publicBookingLabel"
      @created="bookingCreated"
      @authentication-required="requireBookingAuthentication"
      @confirmation-required="reviewPendingAppointment"
      @cancel="bookingOpen = false"
    />
    <p class="public-booking-note">{{ bookingNote }}</p>
  </BaseModal>

  <BookingAuthPrompt
    v-if="authRequiredOpen"
    @login="continueBookingAuthentication('login')"
    @register="continueBookingAuthentication('register')"
    @back="backToAppointment"
  />

  <BaseModal
    v-if="selectedService && selectedServiceDetails"
    :title="selectedService.name"
    eyebrow="Dental service"
    size-class="service-detail-dialog"
    @close="selectedService = null"
  >
    <div class="service-detail-layout">
      <aside class="service-detail-visual">
        <div class="service-detail-mobile-intro">
          <p class="service-detail-lead">{{ selectedServiceDetails.tagline }}</p>
          <p>{{ selectedService.description }}</p>
        </div>
        <p>Healthier smiles start with clear care.</p>
        <div class="service-detail-icon" aria-hidden="true">
          <span
            class="service-art service-art-large"
            :class="serviceArt(selectedService.name)"
          ></span>
        </div>
        <div class="service-detail-visual-badges">
          <span><ShieldCheck :size="20" />Safe care</span>
          <span><HeartHandshake :size="20" />Personal plan</span>
        </div>
      </aside>

      <section class="service-detail-content">
        <p class="service-detail-lead">{{ selectedServiceDetails.tagline }}</p>
        <p>{{ selectedService.description }}</p>

        <div class="service-detail-inclusions">
          <h3>What's included?</h3>
          <ul>
            <li v-for="item in selectedServiceDetails.includes" :key="item">
              <Check :size="16" />{{ item }}
            </li>
          </ul>
        </div>

        <div class="service-detail-facts">
          <div>
            <CalendarDays :size="22" />
            <span
              ><strong>{{ selectedServiceDetails.duration }}</strong
              ><small>Visit timing</small></span
            >
          </div>
          <div>
            <UsersRound :size="22" />
            <span
              ><strong>{{ selectedServiceDetails.audience }}</strong
              ><small>Patient suitability</small></span
            >
          </div>
          <div>
            <ShieldCheck :size="22" />
            <span
              ><strong>{{ selectedServiceDetails.careNote }}</strong
              ><small>Treatment approach</small></span
            >
          </div>
        </div>

        <button class="primary-button full" type="button" @click="bookSelectedService">
          <CalendarCheck2 :size="18" />Book This Service
        </button>
      </section>
    </div>
  </BaseModal>

  <footer id="contact" class="site-footer">
    <a class="footer-brand" href="#home" aria-label="BORJA Dental Clinic home">
      <img class="brand-logo" src="/assets/logo.png" alt="" />
      <span><strong>BORJA</strong><small>Dental Clinic</small></span>
    </a>
    <nav class="footer-links" aria-label="Footer navigation">
      <a href="#home">Home</a>
      <a href="#about">About</a>
      <a href="#services">Services</a>
      <a href="#promos">Promos</a>
      <a href="#feedback">Feedback</a>
      <button type="button" @click="openBooking">Book Appointment</button>
    </nav>
    <div class="footer-contact">
      <strong>A Healthier Smile, A Happier You</strong>
      <span>
        <a href="mailto:doctor@smilecare.local">doctor@smilecare.local</a>
        <a href="tel:+639170002026">0917-000-2026</a>
      </span>
    </div>
  </footer>
  <AuthModal v-if="authOpen" :key="authTab" :initial-tab="authTab" @close="authOpen = false" />
</template>
