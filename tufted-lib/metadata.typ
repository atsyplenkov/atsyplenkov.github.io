/// Escape a string for inclusion in a JSON string value.
#let json-escape(value) = {
  str(value)
    .replace("\\", "\\\\")
    .replace("\"", "\\\"")
    .replace("\n", "\\n")
    .replace("\r", "\\r")
    .replace("\t", "\\t")
}

#let json-string(value) = "\"" + json-escape(value) + "\""

#let json-string-array(values) = {
  if values == none or values.len() == 0 {
    "[]"
  } else {
    "[" + values.map(json-string).join(", ") + "]"
  }
}

#let format-date(date) = {
  if type(date) == datetime {
    date.display("[year]-[month]-[day]")
  } else if type(date) == str {
    date
  } else {
    none
  }
}

#let absolute-url(site-url, path) = {
  if path == none {
    none
  } else if path.starts-with("http://") or path.starts-with("https://") {
    path
  } else if site-url == none {
    none
  } else {
    let base = site-url.trim("/", at: end)
    let clean = path.trim("/", at: start)
    if clean == "" {
      base + "/"
    } else {
      base + "/" + clean
    }
  }
}

#let person-node(person) = {
  if person == none {
    none
  } else {
    (
      "{"
        + "\"@type\": \"Person\", "
        + "\"@id\": "
        + json-string(person.id)
        + ", "
        + "\"name\": "
        + json-string(person.name)
        + ", "
        + "\"url\": "
        + json-string(person.url)
        + ", "
        + "\"sameAs\": "
        + json-string-array(person.same-as)
        + "}"
    )
  }
}

#let json-ld-script(payload) = {
  html.elem(
    "script",
    attrs: (type: "application/ld+json"),
    payload,
  )
}

#let structured-data(
  page-type: "webpage",
  title: "",
  description: none,
  canonical-url: none,
  date: none,
  keywords: (),
  image-url: none,
  lang: "en",
  website-title: "",
  person: none,
) = {
  if canonical-url == none or person == none {
    return
  }

  let person-json = person-node(person)
  let desc = if description == none or description == "" { none } else { description }
  let published = format-date(date)

  if page-type == "blog" {
    let blog = (
      "{"
        + "\"@type\": \"Blog\", "
        + "\"@id\": "
        + json-string(canonical-url + "#blog")
        + ", "
        + "\"name\": "
        + json-string(if title != "" { title } else { website-title })
        + ", "
        + "\"url\": "
        + json-string(canonical-url)
        + ", "
        + "\"inLanguage\": "
        + json-string(lang)
        + ", "
        + "\"publisher\": {\"@id\": "
        + json-string(person.id)
        + "}, "
        + "\"author\": {\"@id\": "
        + json-string(person.id)
        + "}"
        + if desc != none { ", \"description\": " + json-string(desc) } else { "" }
        + "}"
    )
    json-ld-script(
      "{\"@context\": \"https://schema.org\", \"@graph\": [" + blog + ", " + person-json + "]}",
    )
  } else if page-type == "profile" {
    let profile = (
      "{"
        + "\"@type\": \"ProfilePage\", "
        + "\"@id\": "
        + json-string(canonical-url + "#profilepage")
        + ", "
        + "\"url\": "
        + json-string(canonical-url)
        + ", "
        + "\"name\": "
        + json-string(title)
        + ", "
        + "\"mainEntity\": {\"@id\": "
        + json-string(person.id)
        + "}"
        + if desc != none { ", \"description\": " + json-string(desc) } else { "" }
        + "}"
    )
    json-ld-script(
      "{\"@context\": \"https://schema.org\", \"@graph\": [" + profile + ", " + person-json + "]}",
    )
  } else if page-type == "blog-posting" {
    let posting = (
      "{"
        + "\"@type\": \"BlogPosting\", "
        + "\"@id\": "
        + json-string(canonical-url + "#blogposting")
        + ", "
        + "\"headline\": "
        + json-string(title)
        + ", "
        + "\"mainEntityOfPage\": "
        + json-string(canonical-url)
        + ", "
        + "\"url\": "
        + json-string(canonical-url)
        + ", "
        + "\"inLanguage\": "
        + json-string(lang)
        + ", "
        + "\"author\": {\"@id\": "
        + json-string(person.id)
        + "}, "
        + "\"publisher\": {\"@id\": "
        + json-string(person.id)
        + "}"
        + if desc != none { ", \"description\": " + json-string(desc) } else { "" }
        + if published != none { ", \"datePublished\": " + json-string(published) } else { "" }
        + if image-url != none { ", \"image\": " + json-string(image-url) } else { "" }
        + if keywords != none and keywords.len() > 0 {
          ", \"keywords\": " + json-string-array(keywords)
        } else { "" }
        + "}"
    )
    json-ld-script(
      "{\"@context\": \"https://schema.org\", \"@graph\": [" + posting + ", " + person-json + "]}",
    )
  } else {
    let page = (
      "{"
        + "\"@type\": \"WebPage\", "
        + "\"@id\": "
        + json-string(canonical-url + "#webpage")
        + ", "
        + "\"url\": "
        + json-string(canonical-url)
        + ", "
        + "\"name\": "
        + json-string(title)
        + ", "
        + "\"author\": {\"@id\": "
        + json-string(person.id)
        + "}, "
        + "\"publisher\": {\"@id\": "
        + json-string(person.id)
        + "}"
        + if desc != none { ", \"description\": " + json-string(desc) } else { "" }
        + "}"
    )
    json-ld-script(
      "{\"@context\": \"https://schema.org\", \"@graph\": [" + page + ", " + person-json + "]}",
    )
  }
}

#let seo-tags(
  title: "",
  author: none,
  description: none,
  site-url: none,
  canonical-url: none,
  image-path: none,
  image-alt: none,
  page-path: none,
  page-type: "webpage",
  date: none,
  keywords: (),
  website-title: "",
) = {
  let og-image = absolute-url(site-url, image-path)

  let og-type = if page-type == "blog-posting" {
    "article"
  } else if page-type == "profile" {
    "profile"
  } else {
    "website"
  }

  let og-title = if title != "" {
    title
  } else if website-title != "" {
    website-title
  } else {
    "Untitled"
  }

  html.elem("meta", attrs: (property: "og:title", content: og-title))
  html.elem("meta", attrs: (property: "og:type", content: og-type))

  if website-title != none and website-title != "" {
    html.elem("meta", attrs: (property: "og:site_name", content: website-title))
  }

  if description != none and description != "" {
    html.meta(name: "description", content: description)
    html.elem("meta", attrs: (property: "og:description", content: description))
    html.meta(name: "twitter:description", content: description)
  }

  if canonical-url != none {
    html.elem("meta", attrs: (property: "og:url", content: canonical-url))
  }

  if author != none {
    html.meta(name: "author", content: author)
    if og-type == "article" {
      html.elem("meta", attrs: (property: "article:author", content: author))
    }
  }

  let published = format-date(date)
  if published != none and og-type == "article" {
    html.elem("meta", attrs: (property: "article:published_time", content: published))
  }

  if keywords != none and keywords.len() > 0 {
    let joined = keywords.join(", ")
    html.meta(name: "keywords", content: joined)
    for keyword in keywords {
      html.elem("meta", attrs: (property: "article:tag", content: keyword))
    }
  }

  if og-image != none {
    html.elem("meta", attrs: (property: "og:image", content: og-image))
    html.meta(name: "twitter:card", content: "summary_large_image")
    html.meta(name: "twitter:image", content: og-image)
    if image-alt != none and image-alt != "" {
      html.elem("meta", attrs: (property: "og:image:alt", content: image-alt))
      html.meta(name: "twitter:image:alt", content: image-alt)
    }
  } else {
    html.meta(name: "twitter:card", content: "summary")
  }

  html.meta(name: "twitter:title", content: og-title)
}

/// Generate complete page metadata: basic tags, social tags, and JSON-LD.
#let metadata(
  title: "",
  author: none,
  description: "",
  lang: "en",
  date: none,
  website-title: "",
  website-url: none,
  image-path: none,
  image-alt: none,
  feed-dir: (),
  page-type: "webpage",
  keywords: (),
  person: none,
) = {
  html.meta(charset: "utf-8")
  html.meta(name: "viewport", content: "width=device-width, initial-scale=1")
  html.meta(name: "generator", content: "Typst")

  let page-title = if title != "" {
    title
  } else if website-title != "" {
    website-title
  } else {
    "Untitled Page"
  }
  html.title(page-title)
  // Prefer the migrated Quarto SVG favicon; keep ICO for older browsers.
  html.elem(
    "link",
    attrs: (rel: "icon", href: "/assets/favicon.svg", type: "image/svg+xml"),
  )
  html.link(rel: "icon", href: "/assets/favicon.ico")
  // JetBrains Mono for source code (see assets/custom.css).
  html.elem(
    "link",
    attrs: (rel: "preconnect", href: "https://fonts.googleapis.com"),
  )
  html.elem(
    "link",
    attrs: (
      rel: "preconnect",
      href: "https://fonts.gstatic.com",
      crossorigin: "",
    ),
  )
  html.elem(
    "link",
    attrs: (
      rel: "stylesheet",
      href: "https://fonts.googleapis.com/css2?family=JetBrains+Mono:ital,wght@0,400;0,500;0,700;1,400&display=swap",
    ),
  )

  let published = format-date(date)
  if published != none {
    html.meta(name: "date", content: published)
  }

  if feed-dir != none and feed-dir.len() > 0 {
    let rss-title = if website-title != "" { website-title } else { title }
    html.link(
      rel: "alternate",
      type: "application/rss+xml",
      href: "/feed.xml",
      title: rss-title + " RSS Feed",
    )
  }

  let page-path = sys.inputs.at("page-path", default: none)

  let canonical-url = if website-url != none and page-path != none {
    let clean-site-url = website-url.trim("/", at: end)
    let clean-path = page-path.trim("/")
    if clean-path == "" {
      clean-site-url + "/"
    } else {
      clean-site-url + "/" + clean-path + "/"
    }
  } else {
    none
  }

  if canonical-url != none {
    html.link(rel: "canonical", href: canonical-url)
  }

  let resolved-image = if image-path != none {
    image-path
  } else {
    none
  }

  seo-tags(
    title: title,
    author: author,
    description: description,
    site-url: website-url,
    image-path: resolved-image,
    image-alt: image-alt,
    page-path: page-path,
    page-type: page-type,
    date: date,
    keywords: keywords,
    website-title: website-title,
    canonical-url: canonical-url,
  )

  structured-data(
    page-type: page-type,
    title: title,
    description: description,
    canonical-url: canonical-url,
    date: date,
    keywords: keywords,
    image-url: absolute-url(website-url, resolved-image),
    lang: lang,
    website-title: website-title,
    person: person,
  )
}
