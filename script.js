// ─── DOM Ready ───────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initDropZone();
  initLoadingOverlay();
  initFlashDismiss();
  highlightNav();
});

// ─── Drop Zone ────────────────────────────────────────────────────────────────
function initDropZone() {
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('pdf_file');
  const fileInfo  = document.getElementById('file-selected-info');
  const fileName  = document.getElementById('file-name');
  const fileSize  = document.getElementById('file-size');
  const browseBtn = document.getElementById('browse-btn');
  const uploadForm= document.getElementById('upload-form');

  if (!dropZone) return;

  // Browse button click
  browseBtn?.addEventListener('click', () => fileInput.click());
  dropZone.addEventListener('click', (e) => {
    if (e.target === browseBtn || browseBtn?.contains(e.target)) return;
    fileInput.click();
  });

  // File selected via input
  fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) showFileInfo(fileInput.files[0]);
  });

  // Drag & Drop events
  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
  });

  dropZone.addEventListener('dragleave', (e) => {
    if (!dropZone.contains(e.relatedTarget)) {
      dropZone.classList.remove('dragover');
    }
  });

  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length === 0) return;
    const file = files[0];
    if (!validateFile(file)) return;
    const dt = new DataTransfer();
    dt.items.add(file);
    fileInput.files = dt.files;
    showFileInfo(file);
  });

  function showFileInfo(file) {
    if (!validateFile(file)) return;
    fileName.textContent = file.name;
    fileSize.textContent = formatBytes(file.size);
    fileInfo.classList.add('show');
  }

  // Form submit validation
  uploadForm?.addEventListener('submit', (e) => {
    if (!fileInput.files || fileInput.files.length === 0) {
      e.preventDefault();
      showToast('Please select a PDF file first.', 'danger');
      return;
    }
    const file = fileInput.files[0];
    if (!validateFile(file)) {
      e.preventDefault();
      return;
    }
    showLoading();
  });
}

// ─── File Validation ──────────────────────────────────────────────────────────
const MAX_MB = parseInt(document.getElementById('max-mb-data')?.dataset.maxMb || '10', 10);

function validateFile(file) {
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    showToast('Only PDF files are accepted.', 'danger');
    return false;
  }
  const maxBytes = MAX_MB * 1024 * 1024;
  if (file.size > maxBytes) {
    showToast(`File too large. Maximum size is ${MAX_MB} MB.`, 'danger');
    return false;
  }
  return true;
}

function formatBytes(bytes) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// ─── Loading Overlay ──────────────────────────────────────────────────────────
function initLoadingOverlay() {
  // Auto-hide loading if page loads (e.g. browser back button)
  window.addEventListener('pageshow', () => {
    hideLoading();
  });
}

function showLoading() {
  const overlay = document.getElementById('loading-overlay');
  if (!overlay) return;
  overlay.classList.add('show');

  const steps = overlay.querySelectorAll('.loading-step');
  if (!steps.length) return;

  // Animate steps
  const delays = [0, 1800, 4500];
  steps.forEach((step, i) => {
    setTimeout(() => {
      // Mark previous as done
      if (i > 0) {
        steps[i - 1].classList.remove('active');
        steps[i - 1].classList.add('done');
        steps[i - 1].querySelector('.step-icon').textContent = '✓';
      }
      step.classList.add('active');
    }, delays[i]);
  });
}

function hideLoading() {
  const overlay = document.getElementById('loading-overlay');
  overlay?.classList.remove('show');
}

// ─── Flash Message Dismiss ────────────────────────────────────────────────────
function initFlashDismiss() {
  document.querySelectorAll('.flash-alert .btn-close-flash').forEach(btn => {
    btn.addEventListener('click', () => {
      btn.closest('.flash-alert')?.remove();
    });
  });

  // Auto-dismiss after 6 seconds
  document.querySelectorAll('.flash-alert').forEach(alert => {
    setTimeout(() => {
      alert.style.transition = 'opacity 0.5s';
      alert.style.opacity = '0';
      setTimeout(() => alert.remove(), 500);
    }, 6000);
  });
}

// ─── Toast Notification ───────────────────────────────────────────────────────
function showToast(message, type = 'danger') {
  const container = document.getElementById('flash-container');
  if (!container) return;

  const icons = { danger: '⚠️', success: '✅', warning: '⚡' };
  const div = document.createElement('div');
  div.className = `flash-alert ${type} mb-2`;
  div.innerHTML = `
    <span>${icons[type] || '❕'}</span>
    <span>${message}</span>
    <button class="btn-close-flash ms-auto" style="background:none;border:none;cursor:pointer;font-size:1.1rem;color:inherit;">×</button>
  `;

  div.querySelector('.btn-close-flash').addEventListener('click', () => div.remove());
  container.appendChild(div);

  setTimeout(() => {
    div.style.transition = 'opacity 0.5s';
    div.style.opacity = '0';
    setTimeout(() => div.remove(), 500);
  }, 5000);
}

// ─── Active Nav Highlighting ──────────────────────────────────────────────────
function highlightNav() {
  const path = window.location.pathname;
  document.querySelectorAll('.nav-link').forEach(link => {
    const href = link.getAttribute('href');
    if (href === path || (path.startsWith(href) && href !== '/')) {
      link.classList.add('active');
    }
  });
}

// ─── Confirm Delete ───────────────────────────────────────────────────────────
function confirmDelete(policyName) {
  return confirm(`Delete "${policyName}"?\nThis action cannot be undone.`);
}

// ─── Search on Enter ──────────────────────────────────────────────────────────
document.getElementById('search-input')?.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    document.getElementById('search-form')?.submit();
  }
});
