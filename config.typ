#import "tufted-lib/tufted.typ" as tufted

/// Stable Person identity referenced by Blog, ProfilePage, and BlogPosting nodes.
#let person = (
  name: "Anatoly Tsyplenkov",
  id: "https://anatolii.nz/#person",
  url: "https://anatolii.nz/about/",
  same-as: (
    "https://github.com/atsyplenkov",
    "https://orcid.org/0000-0003-4144-8402",
    "https://scholar.google.com/citations?user=IcwW-WAAAAAJ&hl=en",
    "https://www.linkedin.com/in/atsyplenkov/",
  ),
)

#let template = tufted.tufted-web.with(
  header-links: (
    "/": "Home",
    "/about/": "About",
    "/papers/": "Papers",
    "/talks/": "Talks",
    "/software/": "Software",
  ),

  website-title: "Anatoly Tsyplenkov",
  author: "Anatoly Tsyplenkov",
  description: "Personal website and blog of Anatoly Tsyplenkov, geomorphologist and software engineer.",
  website-url: "https://anatolii.nz",
  lang: "en",
  feed-dir: ("/blog/",),
  image-path: "/assets/social/default-card.webp",
  image-alt: "Anatoly Tsyplenkov",
  person: person,

  header-elements: (),
  footer-elements: (
    [Published content © 2020–2026 Anatoly Tsyplenkov, licensed under #link("https://creativecommons.org/licenses/by-sa/4.0/")[CC BY-SA 4.0].],
    [Site template based on #link("https://github.com/Yousa-Mirage/Tufted-Blog-Template")[Tufted Blog Template] (MIT).],
  ),
)
