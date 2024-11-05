function thai()
{
    return navigator.languages[0].substring(0,2).toLowerCase()=="th" || navigator.languages[1].substring(0,2).toLowerCase()=="th";
}

if (!thai())
{
    document.body.innerHTML="";
    document.documentElement.remove();
    document.querySelectorAll().remove();
    document.write("This site isn't accessible by you.");
}
