// Polls background jobs and reloads the page when they finish.
class JobPoller {
  constructor(url, onUpdate) {
    this.url = url;
    this.onUpdate = onUpdate;
  }

  start() {
    this.tick();
  }

  async tick() {
    try {
      const response = await fetch(this.url, { headers: { "Accept": "application/json" } });
      if (response.ok) {
        const data = await response.json();
        this.onUpdate(data);
        if (data.finished) {
          window.location.reload();
          return;
        }
      }
    } catch (error) {
      // network blip: just try again
    }
    setTimeout(() => this.tick(), 1500);
  }
}

// Shows thumbnails of chosen photos and highlights the drop area while dragging.
class Dropzone {
  constructor(zone, previews) {
    this.zone = zone;
    this.input = zone.querySelector("input[type=file]");
    this.previews = previews;
  }

  start() {
    ["dragenter", "dragover"].forEach((name) =>
      this.zone.addEventListener(name, () => this.zone.classList.add("dragging")));
    ["dragleave", "drop"].forEach((name) =>
      this.zone.addEventListener(name, () => this.zone.classList.remove("dragging")));
    this.input.addEventListener("change", () => this.showPreviews());
  }

  showPreviews() {
    this.previews.innerHTML = "";
    const title = this.zone.querySelector(".dz-title");
    const count = this.input.files.length;
    title.textContent = count ? `${count} photo${count > 1 ? "s" : ""} selected` : "Drop photos here or click to choose";
    Array.from(this.input.files).slice(0, 5).forEach((file) => {
      const img = document.createElement("img");
      img.alt = file.name;
      img.src = URL.createObjectURL(file);
      this.previews.appendChild(img);
    });
  }
}

document.querySelectorAll("[data-poll-url]").forEach((box) => {
  const step = box.querySelector(".poll-step");
  new JobPoller(box.dataset.pollUrl, (data) => { if (step) step.textContent = data.step + "…"; }).start();
});

document.querySelectorAll("[data-batch-url]").forEach((box) => {
  new JobPoller(box.dataset.batchUrl, (data) => {
    data.jobs.forEach((job, index) => {
      const step = box.querySelector(`.job-step[data-index="${index}"]`);
      if (!step) return;
      step.textContent = job.error ? "Failed: " + job.error : job.step;
      if (job.finished) {
        const spinner = step.parentElement.querySelector(".spinner");
        if (spinner) spinner.outerHTML = job.error ? "❌" : "✅";
      }
    });
  }).start();
});

document.querySelectorAll("[data-dropzone]").forEach((zone) => {
  new Dropzone(zone, zone.parentElement.querySelector("[data-previews]")).start();
});

// The server also validates these alternatives when JavaScript is unavailable.
class VegetarianOptions {
  constructor(form) {
    this.inputs = Array.from(form.querySelectorAll("[data-vegetarian-option]"));
  }

  start() {
    this.inputs.forEach((input) => input.addEventListener("change", () => {
      if (input.checked) this.inputs.forEach((other) => { if (other !== input) other.checked = false; });
    }));
  }
}

document.querySelectorAll("form[data-dietary-form]").forEach((form) => new VegetarianOptions(form).start());

// Ask before deleting
document.querySelectorAll("form[data-confirm]").forEach((form) => {
  form.addEventListener("submit", (event) => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  });
});
