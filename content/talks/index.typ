#import "../../config.typ": template
#show: template.with(
  title: "Talks",
  description: "Invited talks and workshops by Anatoly Tsyplenkov on landslide connectivity, sediment delivery, and soil erosion modeling in R.",
  page-type: "webpage",
)

= Talks

== IAG Webinar Oceania 2024

On *5 March 2024* during the #link("http://www.geomorph.org/international-geomorphology-week-2024/")[International Geomorphology Week 2024], I gave an invited talk about

#emph[“Data-driven insights on shallow landslide connectivity and sediment delivery to streams”]

#html.div(
  class: "talk-media",
  {
    html.elem(
      "video",
      attrs: (
        controls: "controls",
        preload: "metadata",
        playsinline: "playsinline",
        title: "IAG Webinar Oceania 2024",
      ),
      html.elem(
        "source",
        attrs: (
          src: "https://storage.yandexcloud.net/iag-talk/iag2024_talk_x264.mp4",
          type: "video/mp4",
        ),
        "",
      ),
    )
    html.p(
      class: "talk-media-fallback",
      [Unable to play the recording here? #link("https://storage.yandexcloud.net/iag-talk/iag2024_talk_x264.mp4")[Play or download the IAG recording directly].],
    )
  },
)

== MEGAPOLIS 2022

On *6 December 2022* as a part of the #link("https://megapolis2022.netlify.app/")[Online Young Scientist School MEGAPOLIS 2022], I held a workshop about

#emph[“Soil erosion modeling in R”]

#html.div(
  class: "talk-media",
  html.elem(
    "iframe",
    attrs: (
      src: "https://www.youtube.com/embed/B2ian7Gmodc?si=3IXQ4TLD3Hx8eRLn&start=5569",
      title: "Soil erosion modeling in R",
      loading: "lazy",
      allow: "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture",
      allowfullscreen: "true",
    ),
    "",
  ),
)

#html.p(
  class: "talk-media-fallback",
  [If the embedded video is unavailable, #link("https://www.youtube.com/watch?v=B2ian7Gmodc&t=5569s")[watch the workshop on YouTube].],
)
