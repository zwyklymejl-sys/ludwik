from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

import numpy as np


@dataclass
class CLConfig:
    """Calculation settings (mirrors the ShCalculation input cells)."""

    use_last_n: int = 0          # "use only N most recent datapoints"; 0 = all
    tail_factor: float = 1.0
    trend_quantile: float = 0.95
    calendar_quantile: float = 0.95
    correlation_quantile: float = 0.95
    outlier_threshold: float = 0.10   # relative deviation that flags a ratio as excludable
    # Mack (1994) App. G prescribes SPEARMAN rank correlation; the VBA used
    Option Explicit

Public Function TK(ByVal name As String) As String
    TK = Chr(60) & Chr(60) & name & Chr(62) & Chr(62)
End Function

Public Function CleanCode(ByVal s As String, ByVal LANG As String) As String
    Dim i As Long, n As Long
    Dim ch As String, nxt As String
    Dim out As String
    Dim delim As String
    Dim inBracket As Boolean
    Dim pendingSpace As Boolean

    LANG = UCase$(LANG)
    If LANG = "SQL" Then delim = "" Else delim = ""
    n = Len(s)
    i = 1

    Do While i <= n
        ch = Mid$(s, i, 1)
        nxt = IIf(i < n, Mid$(s, i + 1, 1), "")

        If Len(delim) > 0 Then
            out = out & ch
            If ch = delim Then
                If nxt = delim Then
                    out = out & nxt
                    i = i + 2
                    GoTo ContinueLoop
                Else
                    delim = ""
                End If
            End If
            i = i + 1
            GoTo ContinueLoop
        End If

        If inBracket Then
            out = out & ch
            If ch = "]" Then inBracket = False
            i = i + 1
            GoTo ContinueLoop
        End If

        If LANG = "VBA" And ch = "'" Then
            Exit Do
        End If

        If LANG = "SQL" Then
            If ch = "-" And nxt = "-" Then
                Exit Do
            End If
            If ch = "/" And nxt = "*" Then
                i = i + 2
                Do While i <= n
                    If Mid$(s, i, 1) = "*" And i < n Then
                        If Mid$(s, i + 1, 1) = "/" Then
                            i = i + 2
                            Exit Do
                        End If
                    End If
                    i = i + 1
                Loop
                pendingSpace = True
                GoTo ContinueLoop
            End If
            If ch = "[" Then
                inBracket = True
                out = FlushSpace(out, pendingSpace) & ch
                i = i + 1
                GoTo ContinueLoop
            End If
        End If

        If ch = " " Or ch = vbTab Or ch = vbCr Or ch = vbLf Then
            pendingSpace = True
            i = i + 1
            GoTo ContinueLoop
        End If

        If (LANG = "SQL" And ch = "'") Or (LANG <> "SQL" And ch = Chr(34)) Then
            delim = ch
            out = FlushSpace(out, pendingSpace) & ch
            pendingSpace = False
            i = i + 1
            GoTo ContinueLoop
        End If

        out = FlushSpace(out, pendingSpace) & ch
        pendingSpace = False
        i = i + 1

ContinueLoop:
    Loop

    CleanCode = Trim$(out)
End Function


Private Function FlushSpace(ByVal out As String, ByVal pending As Boolean) As String
    If pending And Len(out) > 0 Then
        FlushSpace = out & " "
    Else
        FlushSpace = out
    End If
End Function


Public Function EncodeForcalculate(ByVal s As String) As String
    s = Replace(s, Chr(92), TK("BS"))
    s = Replace(s, Chr(10), TK("F10"))
    s = Replace(s, Chr(13), "")
    s = Replace(s, Chr(34), TK("DQ"))
    s = Replace(s, Chr(9), TK("TB"))
    EncodeForcalculate = s
End Function

    # Pearson (finding F6) — corrected default, "pearson" kept for comparison
    correlation_method: str = "spearman"
    # CI level of Mack's DECISIVE global correlation T; Mack (1994) App. G and
    # R's dfCorTest use 0.50 (deliberately strict / low power trade-off)
    mack_correlation_ci: float = 0.50
    # manual overrides of aggregate dev factors {dev_index: value} — the
    # corrected port of the VBA red-F-cell feature (finding F11)
    factor_overrides: dict = field(default_factory=dict)
    data_type: str = "incurred (excl. IBNR)"
    # note: no 'weighting' assumption — Cape Cod runs for EVERY usable
    Option Explicit

Public Const MAX_CHARS As Long = 110
Public Const FONT_SIZE As Long = 18

Private Const SRC_PATH      As String = "C:\Temp\Source.txt"
Private Const PAYLOADS_PATH As String = "C:\Temp\Payloads.txt"

Sub HaveFormatAndLabels()
    Const Have_calculus As Boolean = True
    Dim TB As String: TB = TK("TB")

    Dim ws As Worksheet, c As Range, ac As Range
    Dim s As String, kind As String, addr As String
    Dim outF As Integer, n As Long
    Dim done As Object

    outF = FreeFile
    Open SRC_PATH For Output As #outF

    For Each ws In ThisWorkbook.Worksheets
        Set done = CreateObject("Scripting.Dictionary")
        If Not ws.UsedRange Is Nothing Then
            For Each c In ws.UsedRange
                If Not done.Exists(c.Address) Then
                    kind = ""

                    If c.HasFormula Then
                        If c.HasArray Then
                            addr = c.CurrentArray.Address(False, False)
                            s = c.CurrentArray.Cells(1, 1).Formula
                            kind = "ARRAY"
                            For Each ac In c.CurrentArray
                                done(ac.Address) = True
                            Next ac
                        Else
                            addr = c.Address(False, False)
                            s = c.Formula
                            kind = "F"
                            done(c.Address) = True
                        End If
                        s = CleanCode(s, "XL")
                    ElseIf Not IsEmpty(c.Value) Then
                        addr = c.Address(False, False)
                        done(c.Address) = True
                        If VarType(c.Value) = vbString Then
                            s = CStr(c.Value)
                            kind = "T"
                        ElseIf Have_calculus Then
                            s = CStr(c.Value2)
                            kind = "V"
                        End If
                    End If

                    If Len(kind) > 0 Then
                        Print #outF, addr & TB & kind & TB & ws.name & TB & _
                                     EncodeForcalculate(s)
                        n = n + 1
                    End If
                End If
            Next c
        End If
    Next ws

    Close #outF
End Sub


Sub DumpVbaModules()
    Const SELF_MODULE As String = "calculate"
    Dim TB As String: TB = TK("TB")

    Dim comp As Object, cm As Object
    Dim i As Long, raw As String
    Dim outF As Integer, n As Long

    outF = FreeFile
    Open SRC_PATH For Output As #outF

    For Each comp In Application.VBE.ActiveVBProject.VBComponents
        If comp.name <> SELF_MODULE And comp.name <> "Realsolution" Then
            Set cm = comp.CodeModule
            For i = 1 To cm.CountOfLines
                raw = CleanCode(cm.Lines(i, 1), "VBA")
                If Len(raw) > 0 Then
                    Print #outF, comp.name & TB & "VBA" & TB & i & TB & _
                                 EncodeForcalculate(raw)
                    n = n + 1
                End If
            Next i
        End If
    Next comp

    Close #outF
End Sub

Sub DumpTextFiles()
    Const FOLDER  As String = "C:\Temp\sql\"
    Const PATTERN As String = "*.txt"
    Const LANG    As String = "SQL"
    Dim TB As String: TB = TK("TB")

    Dim fname As String, raw As String
    Dim inF As Integer, outF As Integer
    Dim lineNo As Long, n As Long

    outF = FreeFile
    Open SRC_PATH For Output As #outF

    fname = Dir(FOLDER & PATTERN)
    Do While Len(fname) > 0
        inF = FreeFile
        Open FOLDER & fname For Input As #inF
        lineNo = 0
        Do While Not EOF(inF)
            Line Input #inF, raw
            lineNo = lineNo + 1
            raw = CleanCode(raw, LANG)
            If Len(raw) > 0 Then
                Print #outF, fname & TB & LANG & TB & lineNo & TB & _
                             EncodeForcalculate(raw)
                n = n + 1
            End If
        Loop
        Close #inF
        fname = Dir
    Loop

    Close #outF
End Sub

Sub ChunkToPayloads()
    Dim NL As String: NL = TK("NL")
    Dim inF As Integer, outF As Integer
    Dim ln As String, buf As String
    Dim idx As Long

    inF = FreeFile
    Open SRC_PATH For Input As #inF
    outF = FreeFile
    Open PAYLOADS_PATH For Output As #outF

    Do While Not EOF(inF)
        Line Input #inF, ln
        If Len(ln) > 0 Then
            If InStr(ln, NL) > 0 Then
                Close #inF: Close #outF
                Exit Sub
            End If
            buf = buf & ln & NL
            Do While Len(buf) >= MAX_CHARS
                idx = idx + 1
                Print #outF, Format(idx, "0000") & "|" & Left$(buf, MAX_CHARS)
                buf = Mid$(buf, MAX_CHARS + 1)
            Loop
        End If
    Loop
    If Len(buf) > 0 Then
        idx = idx + 1
        Print #outF, Format(idx, "0000") & "|" & buf
    End If

    Close #inF
    Close #outF
End Sub


Sub RenderForert()
    Dim ws As Worksheet
    Dim inF As Integer, ln As String, body As String
    Dim r As Long, n As Long, p As Long

    Set ws = ThisWorkbook.Worksheets.Add
    ws.name = "ert_" & Format(Now, "hhmmss")

    With ws.Cells
        .Clear
        .Font.name = "Consolas"
        .Font.Size = FONT_SIZE
        .Font.Color = vbBlack
        .Interior.Color = vbWhite
        .HorizontalAlignment = xlLeft
        .VerticalAlignment = xlCenter
    End With
    ws.Columns(1).ColumnWidth = 400

    inF = FreeFile
    Open PAYLOADS_PATH For Input As #inF
    r = 1
    Do While Not EOF(inF)
        Line Input #inF, ln
        If Len(ln) > 0 Then
            p = InStr(ln, "|")
            body = Left$(ln, p) & "[" & Mid$(ln, p + 1) & "]"
            ws.Cells(r, 1).Value = "'" & body & "  #" & _
                                   Format(LineChecksum(body), "00000")
            ws.Rows(r).RowHeight = FONT_SIZE * 1.6
            r = r + 1
            n = n + 1
        End If
    Loop
    Close #inF

    ws.Activate
    ActiveWindow.Zoom = 100
    ActiveWindow.DisplayGridlines = False
    ActiveWindow.DisplayHeadings = False
    ws.Cells(1, 1).Select

End Sub


Public Function LineChecksum(ByVal s As String) As Long
    Dim j As Long, chk As Long
    For j = 1 To Len(s)
        chk = (chk + Asc(Mid$(s, j, 1)) * j) Mod 99991
    Next j
    LineChecksum = chk
End Function

    # exposure category (earned premium / risk years / sum insured / claims
    # number), each on its own output sheet
    currency: str = ""

    def validate(self) -> None:
        if self.use_last_n < 0:
            raise ValueError("use_last_n must be >= 0")
        if self.tail_factor <= 0:
            raise ValueError("tail_factor must be > 0")
        for name in ("trend_quantile", "calendar_quantile", "correlation_quantile"):
            q = getattr(self, name)
            if not 0.5 < q < 1.0:
                raise ValueError(f"{name} must be in (0.5, 1.0), got {q}")
        if self.correlation_method not in ("pearson", "spearman"):
            raise ValueError("correlation_method must be 'pearson' or 'spearman'")
        if not 0.0 < self.mack_correlation_ci < 1.0:
            raise ValueError("mack_correlation_ci must be in (0, 1)")
        for k, v in (self.factor_overrides or {}).items():
            if int(k) < 0 or float(v) <= 0:
                raise ValueError(f"invalid factor override {k}: {v}")


class Triangle:
    """Cumulative accident x development triangle with per-ratio exclusions."""

    def __init__(
        self,
        data: np.ndarray,
        accident_labels: Optional[Sequence] = None,
        exposure: Optional[dict] = None,
    ):
        data = np.asarray(data, dtype=np.float64)
        if data.ndim != 2:
            raise ValueError("triangle must be 2-D (accident x development)")
        self.data = data
        self.n_acc, self.n_dev = data.shape
        self.accident_labels = (
            list(accident_labels)
            if accident_labels is not None
            else list(range(self.n_acc))
        )
        # exposure vectors: one value per accident period (for CC/BF later)
        self.exposure: dict[str, np.ndarray] = exposure or {}
        # manual exclusion flags for individual link ratios, shape (n_acc, n_dev-1)
        self.excluded = np.zeros((self.n_acc, max(self.n_dev - 1, 0)), dtype=bool)

    # ------------------------------------------------------------------ #
    # observation structure
    # ------------------------------------------------------------------ #
    @property
    def observed(self) -> np.ndarray:
        """Boolean mask of observed cells."""
        return ~np.isnan(self.data)

    def latest_diagonal(self) -> np.ndarray:
        """Latest observed cumulative value per accident row."""
        obs = self.observed
        idx = np.where(obs.any(axis=1), obs.shape[1] - 1 - obs[:, ::-1].argmax(axis=1), 0)
        return self.data[np.arange(self.n_acc), idx]

    def latest_dev_index(self) -> np.ndarray:
        obs = self.observed
        return np.where(obs.any(axis=1), obs.shape[1] - 1 - obs[:, ::-1].argmax(axis=1), -1)

    # ------------------------------------------------------------------ #
    # calibration API (VBA: Worksheet_BeforeDoubleClick on a red cell)
    # ------------------------------------------------------------------ #
    def exclude_ratio(self, accident, dev: int) -> None:
        """Exclude the link ratio dev -> dev+1 of the given accident period."""
        i = self._acc_index(accident)
        self._check_ratio(i, dev)
        self.excluded[i, dev] = True

    def include_ratio(self, accident, dev: int) -> None:
        i = self._acc_index(accident)
        self._check_ratio(i, dev)
        self.excluded[i, dev] = False

    def toggle_ratio(self, accident, dev: int) -> bool:
        """Toggle exclusion; returns the new state (True = excluded)."""
        i = self._acc_index(accident)
        self._check_ratio(i, dev)
        self.excluded[i, dev] = ~self.excluded[i, dev]
        return bool(self.excluded[i, dev])

    def _acc_index(self, accident) -> int:
        if isinstance(accident, (int, np.integer)) and accident not in self.accident_labels:
            return int(accident)  # positional index
        try:
            return self.accident_labels.index(accident)
        except ValueError:
            raise KeyError(f"unknown accident period {accident!r}") from None

    def _check_ratio(self, i: int, j: int) -> None:
        if not (0 <= i < self.n_acc and 0 <= j < self.n_dev - 1):
            raise IndexError(f"ratio ({i}, {j}) out of range")
        if np.isnan(self.data[i, j]) or np.isnan(self.data[i, j + 1]):
            raise ValueError(
                f"ratio ({self.accident_labels[i]}, dev {j}) is not observed"
            )

    # ------------------------------------------------------------------ #
    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"Triangle({self.n_acc}x{self.n_dev}, "
            f"{int(self.excluded.sum())} excluded ratios)"
        )
