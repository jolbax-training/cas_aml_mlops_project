(function () {
  var root = document.documentElement;
  var slides = Array.prototype.slice.call(document.querySelectorAll("section.slide"));
  var notes = Array.prototype.slice.call(document.querySelectorAll("aside.notes"));
  var counter = document.getElementById("counter");
  var index = 0;
  root.classList.add("js-deck");
  function show(next) {
    index = Math.max(0, Math.min(slides.length - 1, next));
    slides.forEach(function (slide, i) { slide.classList.toggle("current", i === index); });
    notes.forEach(function (note, i) { note.classList.toggle("current", i === index); });
    counter.textContent = (index + 1) + " / " + slides.length;
    history.replaceState(null, "", "#" + (index + 1));
  }
  document.addEventListener("keydown", function (event) {
    if (event.altKey || event.ctrlKey || event.metaKey) { return; }
    var key = event.key;
    if (key === "ArrowRight" || key === " " || key === "PageDown") { show(index + 1); }
    else if (key === "ArrowLeft" || key === "PageUp") { show(index - 1); }
    else if (key === "Home") { show(0); }
    else if (key === "End") { show(slides.length - 1); }
    else if (key === "n" || key === "N") { root.classList.toggle("show-notes"); return; }
    else if ((key === "f" || key === "F") && root.requestFullscreen) { root.requestFullscreen(); }
    else { return; }
    event.preventDefault();
  });
  var start = parseInt(location.hash.slice(1), 10);
  show(isNaN(start) ? 0 : start - 1);
})();
