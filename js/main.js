// Simple Bootstrap form validation
(function(){
  const forms = document.querySelectorAll('.needs-validation');
  forms.forEach(f => f.addEventListener('submit', e => {
    if(!f.checkValidity()){ e.preventDefault(); e.stopPropagation(); }
    f.classList.add('was-validated');
  }));
})();
