# Ayudante de mando_raton.py: vigila con UI Automation y escribe líneas en stdout.
#   FOCO EDIT x y ancho alto    el elemento con foco es un campo de texto (y dónde está en pantalla)
#   FOCO OTRO <descripción>     no lo es; la descripción sirve para saber por qué no se abrió el teclado
# Por stdin recibe "PUNTO x y" tras cada clic: si el foco no quedó en un campo pero debajo del clic
# hay uno (Claude, Discord y otros programas dejan el foco en el contenedor), avisa FOCO EDIT igual.
param([int]$Padre = 0)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes, WindowsBase
$AE = [System.Windows.Automation.AutomationElement]
$CT = [System.Windows.Automation.ControlType]
$PV = [System.Windows.Automation.ValuePattern]::Pattern
$PT = [System.Windows.Automation.TextPattern]::Pattern
$NO_TEXTO = @($CT::Slider, $CT::Spinner, $CT::ScrollBar, $CT::ProgressBar, $CT::Hyperlink)

function Es-Texto($e) {
    if (-not $e) { return $false }
    $c = $e.Current
    if ($c.ClassName -eq 'OSKMainClass') { return $null }  # teclado de Windows: no cambia nada
    $vp = $null
    $conValor = $e.TryGetCurrentPattern($PV, [ref]$vp)
    # Campos de texto: tipo Edit, o controles clásicos cuya clase lo dice (EDIT, RichEdit)
    if ($c.ControlType -eq $CT::Edit -or $c.ClassName -match '(?i)^(edit|richedit)|\.edit\.') {
        if ($conValor) { return -not $vp.Current.IsReadOnly }
        return $true
    }
    # Cajas de búsqueda web (YouTube, Google...): el navegador las expone como ComboBox editable
    if ($c.ControlType -eq $CT::ComboBox) {
        if ($conValor) { return -not $vp.Current.IsReadOnly }
        return $false
    }
    # Campos web editables que no son de tipo Edit (chats, comentarios, correos: contenteditable):
    # el navegador les da un valor que se puede escribir...
    if ($conValor -and -not $vp.Current.IsReadOnly -and $c.IsKeyboardFocusable -and
        $NO_TEXTO -notcontains $c.ControlType) {
        return $true
    }
    # ...o, si no tienen valor (un div contenteditable sale como Group), su texto dice que no es
    # de solo lectura. La página normal y los bloques no editables dicen que sí lo es.
    $tp = $null
    if (-not $conValor -and $c.IsKeyboardFocusable -and $NO_TEXTO -notcontains $c.ControlType -and
        $e.TryGetCurrentPattern($PT, [ref]$tp)) {
        $soloLectura = $tp.DocumentRange.GetAttributeValue([System.Windows.Automation.TextPattern]::IsReadOnlyAttribute)
        if ($soloLectura -is [bool] -and -not $soloLectura) { return $true }
    }
    return $false
}

function Describir($e) {
    $c = $e.Current
    $v = 'sinValor'
    $vp = $null
    if ($e.TryGetCurrentPattern($PV, [ref]$vp)) {
        $v = if ($vp.Current.IsReadOnly) { 'valorSoloLectura' } else { 'valorEscribible' }
    }
    $tp = $null
    $t = if ($e.TryGetCurrentPattern($PT, [ref]$tp)) { 'conTexto' } else { 'sinTexto' }
    # Solo etiquetas cortas de controles (Buscar, Mensaje...). Nunca el nombre de páginas, ventanas,
    # enlaces o textos: ahí va el título de la página o del contenido que estás viendo.
    $n = ''
    if (@($CT::Edit, $CT::ComboBox, $CT::Group, $CT::Custom, $CT::Button) -contains $c.ControlType) {
        $n = ("" + $c.Name) -replace '\s+', ' '
        if ($n.Length -gt 25) { $n = $n.Substring(0, 25) }
    }
    "$($c.ControlType.ProgrammaticName) clase=$($c.ClassName) marco=$($c.FrameworkId) $v $t enfocable=$($c.IsKeyboardFocusable) nombre=$n"
}

function Linea-Edit($e) {
    $r = $e.Current.BoundingRectangle
    $l = 'FOCO EDIT'
    if (-not $r.IsEmpty -and -not [double]::IsInfinity($r.X)) {
        $l += " $([int]$r.X) $([int]$r.Y) $([int]$r.Width) $([int]$r.Height)"
    }
    $l
}

function Campo-En($x, $y) {
    # El elemento bajo el punto o uno de sus padres (hasta la ventana) que sea un campo de texto
    $e = $AE::FromPoint((New-Object System.Windows.Point($x, $y)))
    $w = [System.Windows.Automation.TreeWalker]::ControlViewWalker
    for ($i = 0; $e -and $i -lt 10; $i++) {
        $c = $e.Current
        if ($c.ControlType -eq $CT::Window) { break }
        if (Es-Texto $e) { return $e }
        $e = $w.GetParent($e)
    }
    return $null
}

# Lectura de stdin sin bloquear: ReadLineAsync y mirar si terminó en cada vuelta
$lector = $null
$tarea = $null
try {
    $lector = New-Object System.IO.StreamReader([Console]::OpenStandardInput(), [System.Text.Encoding]::UTF8)
    $tarea = $lector.ReadLineAsync()
} catch { $tarea = $null }
$punto = $null
$puntoT = [DateTime]::MinValue

$focoPrevio = ''
$clavePrevia = ''
$vueltas = 0
while ($true) {
    # Terminar si mando_raton.py ya no existe
    if ($Padre -and (++$vueltas % 10 -eq 0) -and -not (Get-Process -Id $Padre -ErrorAction SilentlyContinue)) { exit }
    try {
        if ($tarea -and $tarea.IsCompleted) {
            $l = $null
            try { $l = $tarea.Result } catch {}
            if ($null -eq $l) { $tarea = $null }   # stdin cerrado
            else {
                if ($l -match '^PUNTO (-?\d+) (-?\d+)') {
                    $punto = @([double]$matches[1], [double]$matches[2])
                    $puntoT = [DateTime]::Now.AddMilliseconds(250)   # que el foco se asiente
                }
                $tarea = $lector.ReadLineAsync()
            }
        }
        if ($punto -and [DateTime]::Now -ge $puntoT) {
            $p = $punto
            $punto = $null
            $f = $AE::FocusedElement
            if (-not ($f -and (Es-Texto $f))) {
                $campo = Campo-En $p[0] $p[1]
                if ($campo) {
                    $linea = Linea-Edit $campo
                    [Console]::Out.WriteLine($linea); [Console]::Out.Flush(); $focoPrevio = $linea
                }
            }
        }
    } catch {}
    try {
        $f = $AE::FocusedElement
        if ($f) {
            $r = $f.Current.BoundingRectangle
            $clave = (($f.GetRuntimeId()) -join '.') + "|$r"
            if ($clave -ne $clavePrevia) {
                $clavePrevia = $clave
                $t = Es-Texto $f
                if ($null -ne $t) {
                    if ($t) {
                        $linea = Linea-Edit $f
                    } else {
                        $linea = 'FOCO OTRO ' + (Describir $f)
                    }
                    if ($linea -ne $focoPrevio) { [Console]::Out.WriteLine($linea); [Console]::Out.Flush(); $focoPrevio = $linea }
                }
            }
        }
    } catch {}
    Start-Sleep -Milliseconds 100
}
